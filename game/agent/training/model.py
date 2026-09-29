"""Small CPU graph actor-critic; every action uses the same candidate scorer."""
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn

from game.agent.contracts import full as f
from game.agent.action_policy import ALL_LEGAL, validate_policy
from .features import Vocabulary


@dataclass(frozen=True, slots=True)
class Architecture:
    hidden_size: int = 48
    message_layers: int = 2
    schema: str = 'sts_graph_actor_critic_v1'

    def __post_init__(self):
        if (self.schema != 'sts_graph_actor_critic_v1' or type(self.hidden_size) is not int or
                not 8 <= self.hidden_size <= 128 or type(self.message_layers) is not int or
                not 1 <= self.message_layers <= 4):
            raise ValueError('Unsupported model architecture')


def collate(states, *, vocabulary):
    if not states or any(s.vocabulary != vocabulary.identity for s in states):
        raise ValueError('Expected nonempty batch with one frozen vocabulary')
    if len({s.action_policy for s in states}) != 1:
        raise ValueError('Mixed policy-action versions in one batch')
    rows = {key: [] for key in ('nodes', 'parents', 'positions', 'fields', 'numbers', 'links',
                                'link_positions', 'owners', 'roots')}
    counts = [len(s.candidates) for s in states]
    if min(counts) < 1:
        raise ValueError('Terminal observations have no categorical distribution')
    candidates = np.zeros((len(states), max(counts), 3), dtype=np.int64)
    candidates[:, :, 1:] = -1
    mask = np.zeros((len(states), max(counts)), dtype=np.bool_)
    offset = 0
    for owner, state in enumerate(states):
        validate_policy(state.action_policy)
        if (type(state.policy_mask) is not tuple or len(state.policy_mask) != counts[owner] or
                any(type(v) is not bool for v in state.policy_mask) or not any(state.policy_mask)):
            raise ValueError('Invalid policy action mask')
        n = len(state.nodes)
        for key in ('nodes', 'positions', 'numbers', 'link_positions'):
            rows[key].append(getattr(state, key))
        parent = state.parents.copy().reshape(-1)
        parent[parent >= 0] += offset
        rows['parents'].append(parent)
        fields, links, actions = state.fields.copy(), state.links.copy(), state.candidates.copy()
        fields[:, 0] += offset
        links[:, 0] += offset
        links[links[:, 2] >= 0, 2] += offset
        actions[:, 1:] = np.where(actions[:, 1:] >= 0, actions[:, 1:] + offset, -1)
        rows['fields'].append(fields)
        rows['links'].append(links)
        rows['owners'].append(np.full(n, owner, dtype=np.int64))
        rows['roots'].append(np.array(state.roots, dtype=np.int64).reshape(1, 2) + offset)
        candidates[owner, :counts[owner]], mask[owner, :counts[owner]] = actions, state.policy_mask
        offset += n
    batch = {key: torch.from_numpy(np.concatenate(value, axis=0)) for key, value in rows.items()}
    batch.update(candidates=torch.from_numpy(candidates), mask=torch.from_numpy(mask))
    return batch


def _pool(values, owners, count):
    total = values.new_zeros((count, values.shape[-1])).index_add(0, owners, values)
    sizes = values.new_zeros(count).index_add(0, owners, values.new_ones(len(values)))
    return total / sizes.clamp_min(1).unsqueeze(-1), sizes


def _linked(values, indexes):
    return values[indexes.clamp_min(0)] * (indexes >= 0).unsqueeze(-1)


class ActorCritic(nn.Module):
    def __init__(self, vocabulary: Vocabulary, architecture=Architecture(), *, seed=0, action_policy=ALL_LEGAL):
        super().__init__()
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError('Model seed must be a nonnegative int64')
        self.vocabulary, self.architecture = vocabulary, architecture
        self.action_policy = validate_policy(action_policy)
        d = architecture.hidden_size
        # Initialization must not alter the caller's global torch RNG.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            self.name = nn.Embedding(len(vocabulary.names) + 1, d)
            self.field_type = nn.Embedding(4, d)
            self.namespace = nn.Embedding(len(f.NAMESPACES) + 1, d)
            self.action = nn.Embedding(len(f.ACTIONS), d)
            self.number = nn.Linear(2, d)
            self.position = nn.Linear(2, d)
            self.link_position = nn.Linear(3, d)
            self.counts = nn.Linear(2, d)
            self.field = nn.Sequential(nn.Linear(d, d), nn.Tanh())
            self.base = nn.Sequential(nn.Linear(d * 3, d), nn.Tanh())
            self.messages = nn.ModuleList(nn.Sequential(nn.Linear(d * 4, d), nn.Tanh(), nn.LayerNorm(d))
                                          for _ in range(architecture.message_layers))
            self.state = nn.Sequential(nn.Linear(d * 3, d), nn.Tanh())
            self.scorer = nn.Sequential(nn.Linear(d * 4 + 2, d), nn.Tanh(), nn.Linear(d, 1))
            self.value = nn.Sequential(nn.Linear(d, d), nn.Tanh(), nn.Linear(d, 1))

    def forward(self, batch):
        nodes, fields, links = batch['nodes'], batch['fields'], batch['links']
        n = len(nodes)
        field_values = self.field(self.name(fields[:, 1]) + self.field_type(fields[:, 2]) +
                                  self.name(fields[:, 3]) * (fields[:, 2] == 3).unsqueeze(-1) +
                                  self.number(batch['numbers']))
        attributes, field_counts = _pool(field_values, fields[:, 0], n)
        parent = batch['parents']
        child_indexes = torch.nonzero(parent >= 0, as_tuple=True)[0]
        child_counts = torch.bincount(parent[child_indexes], minlength=n).to(attributes.dtype)
        h = self.base(torch.cat((self.name(nodes[:, 0]), self.name(nodes[:, 1]), attributes), -1))
        h = h + self.position(batch['positions']) + self.counts(torch.stack(
            (torch.log1p(field_counts), torch.log1p(child_counts)), -1))
        for layer in self.messages:
            children, _ = _pool(h[child_indexes], parent[child_indexes], n)
            linked = _linked(h, links[:, 2]) + self.name(links[:, 1]) + self.namespace(links[:, 3])
            linked = linked + self.link_position(batch['link_positions'])
            linked, _ = _pool(torch.tanh(linked), links[:, 0], n)
            h = h + layer(torch.cat((h, children, _linked(h, parent), linked), -1))
        pooled, _ = _pool(h, batch['owners'], len(batch['roots']))
        state = self.state(torch.cat((pooled, h[batch['roots'][:, 0]], h[batch['roots'][:, 1]]), -1))
        a = batch['candidates']
        state_actions = state[:, None, :].expand(-1, a.shape[1], -1)
        logits = self.scorer(torch.cat((state_actions, self.action(a[:, :, 0]),
            _linked(h, a[:, :, 1]), _linked(h, a[:, :, 2]), (a[:, :, 1:] >= 0).to(h.dtype)), -1)).squeeze(-1)
        return logits, self.value(state).squeeze(-1)


def log_probabilities(logits, mask):
    if (mask.dtype is not torch.bool or logits.shape != mask.shape or logits.ndim != 2 or
            not mask.any(-1).all() or not torch.isfinite(logits[mask]).all()):
        raise ValueError('Invalid/nonfinite logits or an all-masked policy row')
    return torch.log_softmax(logits.masked_fill(~mask, -torch.inf), -1)


def policy_statistics(logits, mask, actions):
    logp = log_probabilities(logits, mask)
    if (actions.dtype != torch.long or actions.shape != (len(logits),) or
            (actions < 0).any() or (actions >= logits.shape[1]).any() or
            not mask.gather(1, actions[:, None]).all()):
        raise ValueError('Invalid action for the original legal mask')
    entropy = -(logp.exp() * torch.where(mask, logp, 0)).sum(-1)
    return logp.gather(1, actions[:, None]).squeeze(-1), entropy


def sample_actions(logits, mask, *, generator):
    if type(generator) is not torch.Generator:
        raise ValueError('Sampling requires an explicit learner generator')
    return torch.multinomial(log_probabilities(logits, mask).exp(), 1, generator=generator).squeeze(-1)
