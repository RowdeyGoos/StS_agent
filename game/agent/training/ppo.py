"""Project-owned CPU PPO: one frozen collection batch, then bounded updates."""
import math
import time

import torch

from .model import collate, policy_statistics
from .ppo_config import PPOExperiment
from .rollout import advantages, check_cancel, collect, fingerprint

UPDATE_POLICY = 'skip_zero_signal_v1'


def check_budget(cancel, deadline):
    check_cancel(cancel)
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('PPO update exceeded the experiment time budget')


def normalize(values):
    if not torch.isfinite(values).all():
        raise ValueError('Nonfinite advantages')
    deviation = values.std(unbiased=False)
    # A singleton/constant batch must not become NaN or lose all its signal.
    return (values-values.mean())/deviation.clamp_min(1e-8) if deviation > 1e-8 else values


def objective(logp, old_logp, advantage, values, returns, entropy, config):
    arrays = (logp, old_logp, advantage, values, returns, entropy)
    if (logp.ndim != 1 or not len(logp) or any(x.shape != logp.shape or not torch.isfinite(x).all() for x in arrays)
            or any(x.requires_grad for x in (old_logp, advantage, returns))):
        raise ValueError('Invalid PPO loss inputs')
    log_ratio = logp-old_logp
    ratio = log_ratio.exp()
    policy_loss = -torch.minimum(ratio*advantage, ratio.clamp(1-config.clip_ratio, 1+config.clip_ratio)*advantage).mean()
    value_loss = (values-returns).square().mean()
    loss = policy_loss + config.value_weight*value_loss - config.entropy_weight*entropy.mean()
    metrics = {'policy_loss':policy_loss, 'value_mse':value_loss, 'entropy':entropy.mean(),
               'approx_kl':((ratio-1)-log_ratio).mean(),
               'clip_fraction':((ratio-1).abs()>config.clip_ratio).float().mean(), 'loss':loss}
    if any(not torch.isfinite(x) for x in metrics.values()):
        raise ValueError('Nonfinite PPO objective')
    return loss, metrics


def replay_batch(steps, vocabulary, *, action_policy=None):
    for step in steps:
        if (step.candidate_refs != step.state.candidate_refs or
                step.mask != step.state.policy_mask or
                action_policy is not None and step.state.action_policy != action_policy or
                any(permitted and not legal for permitted, legal in
                    zip(step.mask, step.state.legal_mask)) or
                len(step.mask) != len(step.state.legal_mask) or
                len(step.mask) != len(step.state.candidates) or type(step.action) is not int or
                not 0 <= step.action < len(step.mask) or not step.mask[step.action] or
                not math.isfinite(step.old_log_probability) or step.old_log_probability > 0):
            raise ValueError('Corrupt original rollout mapping, mask or likelihood')
    batch = collate([s.state for s in steps], vocabulary=vocabulary)
    mask = torch.zeros_like(batch['mask'])
    for i, step in enumerate(steps):
        mask[i, :len(step.mask)] = torch.tensor(step.mask)
    if not torch.equal(mask, batch['mask']):
        raise ValueError('Replayed policy mask differs from collection')
    batch['mask'] = mask
    return batch


class PPOLearner:
    """Single synchronous owner; resume only with no pending game or rollout."""
    def __init__(self, model, experiment=PPOExperiment(), *, seed=0, cursor=0, env_factory=None, workers=1):
        from .parallel import collection_settings
        from .scenarios import episode_seed, SCENARIO_SET
        if type(experiment) is not PPOExperiment or type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError('Invalid PPO experiment or learner seed')
        episode_seed('train', cursor)
        if env_factory is None and experiment.source == 'ironclad_a0_curriculum_v1':
            from .curriculum import environment
            env_factory = environment
        if env_factory is None and experiment.training.mode == 'full_run':
            from .run_task import environment
            env_factory = environment
        if (env_factory is None) != (experiment.source == SCENARIO_SET):
            raise ValueError('Custom collection requires a distinct source and environment factory')
        from .combat_corpus import validate_factory
        validate_factory(experiment, env_factory)
        if next(model.parameters()).device.type != 'cpu':
            raise ValueError('PPO currently supports CPU')
        if model.action_policy != experiment.training.action_policy:
            raise ValueError('PPO model and experiment policy-action versions differ')
        self.model, self.experiment, self.env_factory = model, experiment, env_factory
        self.config = experiment.ppo
        self.model.requires_grad_(True)
        self.optimizer = torch.optim.Adam(model.parameters(), lr=self.config.learning_rate, foreach=False)
        self.action_generator = torch.Generator().manual_seed(seed)
        self.update_generator = torch.Generator().manual_seed((seed+1) % 2**63)
        self.episode_cursor = cursor
        self.decisions = self.iterations = self.updates = 0
        self.skipped_iterations = 0
        self.phase, self.pending = 'boundary', None
        self.latest_collection = {}
        self.collection_settings = collection_settings(workers)
        self.collector, self.closed = None, False

    def close(self):
        self.closed = True
        if self.collector is not None:
            try:
                self.collector.close()
            except BaseException:
                self.phase = 'failed'
                raise

    def __enter__(self):
        if self.closed:
            raise ValueError('PPO learner is closed')
        return self

    def __exit__(self, *_):
        self.close()

    def collect(self, *, decisions=None, output_dir=None, audit_dir=None, cancel=None, deadline=None):
        if self.closed or self.phase != 'boundary':
            raise ValueError('Collection requires a clean learner boundary')
        self.phase = 'collecting'
        self.latest_collection = {}
        try:
            settings = dict(cursor=self.episode_cursor, iteration=self.iterations, decisions=decisions,
                output_dir=output_dir, audit_dir=audit_dir, cancel=cancel, deadline=deadline,
                progress=self.latest_collection)
            if self.collection_settings['workers'] == 1:
                result = collect(self.model, self.experiment, self.action_generator,
                                 env_factory=self.env_factory, **settings)
            else:
                from .parallel import ParallelCollector
                if self.collector is None:
                    self.collector = ParallelCollector(self.model, self.experiment, self.env_factory,
                                                       self.collection_settings['workers'])
                result = self.collector.collect(self.model, self.action_generator, **settings)
            self.pending, self.phase = result, 'collected'
            return result
        except BaseException:
            self.phase = 'failed'
            self.close()
            raise

    def update(self, rollout, *, cancel=None, deadline=None):
        if (self.closed or self.phase != 'collected' or self.pending is not rollout or not rollout.steps or
                rollout.behavior != fingerprint(self.model) or rollout.iteration != self.iterations or
                rollout.experiment != self.experiment.identity):
            raise ValueError('PPO requires its current, nonempty frozen-policy rollout')
        self.phase = 'updating'
        started, start_updates = time.perf_counter(), self.updates
        config, steps = self.config, rollout.steps
        metrics, weight, max_norm, peak_batch = {}, 0, 0.0, 0
        try:
            adv, returns = advantages(steps, gamma=config.gamma, gae_lambda=config.gae_lambda)
            training_adv = normalize(adv) if config.normalize_advantages else adv
            signal = {'policy':UPDATE_POLICY, 'nonzero_advantages':int(torch.count_nonzero(adv)),
                      'nonzero_returns':int(torch.count_nonzero(returns)),
                      'nonzero_rewards':sum(s.reward != 0 for s in steps),
                      'replayed_nonzero_value_errors':None}
            last, stopped, skipped, epochs = {}, False, False, 0
            if signal['nonzero_advantages'] == 0:
                # Check actual predictions and every original action mapping.
                # Mean squared error can underflow; count residuals directly.
                last = self._measure(steps, training_adv, returns, cancel=cancel,
                                     deadline=deadline, signal=signal)
                skipped = signal['replayed_nonzero_value_errors'] == 0
            for epoch in range(0 if skipped else config.epochs):
                epochs = epoch+1
                order = torch.randperm(len(steps), generator=self.update_generator)
                for start in range(0, len(order), config.batch_size):
                    check_budget(cancel, deadline)
                    indexes = order[start:start+config.batch_size]
                    rows = [steps[i] for i in indexes.tolist()]
                    batch = replay_batch(rows, self.model.vocabulary, action_policy=self.model.action_policy)
                    self.model.train()
                    logits, values = self.model(batch)
                    logp, entropy = policy_statistics(logits, batch['mask'], torch.tensor([s.action for s in rows]))
                    loss, parts = objective(logp, torch.tensor([s.old_log_probability for s in rows]),
                        training_adv[indexes], values, returns[indexes], entropy, config)
                    self.optimizer.zero_grad(set_to_none=True)
                    loss.backward()
                    norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), config.gradient_clip,
                                                         error_if_nonfinite=True)
                    self.optimizer.step()
                    self.updates += 1
                    if any(not torch.isfinite(p).all() for p in self.model.parameters()):
                        raise ValueError('Nonfinite PPO parameters')
                    for key, value in parts.items():
                        metrics[key] = metrics.get(key, 0.0)+value.item()*len(rows)
                    weight += len(rows)
                    max_norm = max(max_norm, norm.item())
                    peak_batch = max(peak_batch, sum(t.numel()*t.element_size() for t in batch.values()))
                # Measure divergence over the entire original batch after this
                # epoch. This is a stopping heuristic, not a hard KL constraint.
                last = self._measure(steps, training_adv, returns, cancel=cancel, deadline=deadline)
                if last['approx_kl'] > config.target_kl:
                    stopped = True
                    break
            check_budget(cancel, deadline)
            self.episode_cursor = rollout.next_episode
            self.decisions += len(steps)
            self.iterations += 1
            self.skipped_iterations += int(skipped)
            self.pending, self.phase = None, 'boundary'
            return {'iteration':self.iterations, 'optimizer_steps':self.updates-start_updates,
                    'optimizer_steps_total':self.updates, 'decisions':len(steps), 'epochs':epochs,
                    'status':'skipped' if skipped else 'updated',
                    'skip_reason':'zero_advantages_and_value_errors' if skipped else None,
                    'signal':signal,
                    'kl_early_stop':stopped, 'mean_update':{k:v/weight for k,v in metrics.items()},
                    'after':last, 'max_gradient_norm':max_norm, 'batch_input_tensor_bytes':peak_batch,
                    'packed_rollout_bytes':sum(s.state.nbytes for s in steps),
                    'seconds':time.perf_counter()-started}
        except BaseException:
            self.phase = 'failed'
            self.close()
            raise

    def _measure(self, steps, adv, returns, *, cancel=None, deadline=None, signal=None):
        result = {}
        if signal is not None:
            signal['replayed_nonzero_value_errors'] = 0
        self.model.eval()
        with torch.inference_mode():
            for start in range(0, len(steps), self.config.batch_size):
                check_budget(cancel, deadline)
                rows = steps[start:start+self.config.batch_size]
                batch = replay_batch(rows, self.model.vocabulary, action_policy=self.model.action_policy)
                logits, values = self.model(batch)
                logp, entropy = policy_statistics(logits, batch['mask'], torch.tensor([s.action for s in rows]))
                _, metrics = objective(logp, torch.tensor([s.old_log_probability for s in rows]),
                    adv[start:start+len(rows)], values, returns[start:start+len(rows)], entropy, self.config)
                if signal is not None:
                    signal['replayed_nonzero_value_errors'] += int(torch.count_nonzero(
                        values-returns[start:start+len(rows)]))
                for key, value in metrics.items():
                    result[key] = result.get(key, 0.0)+value.item()*len(rows)/len(steps)
        return result
