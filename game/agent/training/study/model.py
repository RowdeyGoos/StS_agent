"""Four capacity-measurable actors over exactly the same semantic arrays."""
from dataclasses import replace
import numpy as np
import torch
from torch import nn
from game.agent.contracts.full import ACTIONS
from game.agent.input_views import RAW
from .spec import FeatureSpec, StudyArchitecture, channels
from .projection import StudyFeatures, StudyEncoder


def collate_study(states, vocabulary):
    from .compact import CompactFeatures, collate_compact
    if states and isinstance(states[0], CompactFeatures):
        return collate_compact(states, vocabulary)
    if (not states or any(type(s) is not StudyFeatures or s.vocabulary != vocabulary.identity for s in states)
            or len({(s.feature_identity, s.capacity, s.action_policy) for s in states}) != 1):
        raise ValueError('Mixed study feature semantics')
    capacity, width = states[0].capacity, states[0].values.shape[1]
    n, a = len(states), max(len(s.candidates) for s in states)
    values = np.zeros((n, capacity, width), dtype=np.float32)
    identities = np.zeros((n, capacity), dtype=np.int64)
    present = np.zeros((n, capacity), dtype=np.bool_)
    candidates = np.full((n, a, 3), -1, dtype=np.int64)
    mask = np.zeros((n, a), dtype=np.bool_)
    adjacency = np.zeros((n, capacity, capacity), dtype=np.float32)
    for i, s in enumerate(states):
        size, count = len(s.values), len(s.candidates)
        if (not 0 < size <= capacity or s.values.shape != (size, width) or s.values.dtype != np.float32
                or not np.isfinite(s.values).all() or s.identities.shape != (size,)
                or s.identities.dtype != np.int64 or (s.identities < 0).any()
                or (s.identities > len(vocabulary.names)).any()
                or s.parents.shape != (size,) or s.parents.dtype != np.int64
                or ((s.parents < -1) | (s.parents >= size)).any()
                or s.candidates.shape != (count, 3) or s.candidates.dtype != np.int64
                or len(s.policy_mask) != count or not any(s.policy_mask)
                or len(s.legal_mask) != count or len(s.candidate_refs) != count
                or any(type(v) is not bool for v in (*s.policy_mask, *s.legal_mask))
                or any(p and not l for p, l in zip(s.policy_mask, s.legal_mask))
                or len(set(s.candidate_refs)) != count
                or ((s.candidates[:, 1:] < -1) | (s.candidates[:, 1:] >= size)).any()
                or ((s.candidates[:, 0] < 0) | (s.candidates[:, 0] >= len(ACTIONS))).any()):
            raise ValueError('Invalid study entities, operands or masks')
        values[i, :size], identities[i, :size], present[i, :size] = s.values, s.identities, True
        candidates[i, :count], mask[i, :count] = s.candidates, s.policy_mask
        for child, parent in enumerate(s.parents):
            if parent >= 0:
                adjacency[i, child, parent] = adjacency[i, parent, child] = 1
        for _, subject, target in s.candidates:
            if subject >= 0 and target >= 0:
                adjacency[i, subject, target] = adjacency[i, target, subject] = 1
    adjacency /= np.maximum(adjacency.sum(-1, keepdims=True), 1)
    return {**{k: torch.from_numpy(v) for k, v in dict(study_values=values, identities=identities,
            present=present, candidates=candidates, mask=mask, adjacency=adjacency).items()},
            'feature_identity': states[0].feature_identity}


class StudyActorCritic(nn.Module):
    def __init__(self, vocabulary, architecture, *, seed=0, action_policy, input_view=RAW):
        super().__init__()
        from game.agent.action_policy import validate_policy
        validate_policy(action_policy)
        if type(seed) is not int or not 0 <= seed < 2**63:
            raise ValueError('Invalid study initialization seed')
        if input_view != RAW:
            raise ValueError('Study uses its own detached public history specification')
        self.vocabulary, self.architecture = vocabulary, architecture
        self.spec = FeatureSpec.from_dict(architecture.features)
        self.action_policy, self.input_view = action_policy, input_view
        if self.spec.identities != bool(vocabulary.names) or vocabulary.catalog is not None:
            raise ValueError('Study vocabulary must contain only optional content identities')
        self.feature_identity = architecture.identity(vocabulary)
        d = architecture.hidden_size
        width = len(channels(self.spec.richness)) + (8 if self.spec.identities else 0)
        self.input_width = width
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            from .spec import COMPACT_ARCHITECTURES
            if architecture.kind in COMPACT_ARCHITECTURES:
                from .compact import CompactNetwork
                self.compact_network = CompactNetwork(architecture)
                return
            if self.spec.identities:
                self.content = nn.Embedding(len(vocabulary.names), 8)
            if architecture.kind == 'flat_mlp':
                # Exactly two fully connected hidden layers per candidate and
                # value. Splitting the first matrix avoids repeating its large
                # state product; this is algebraically ordinary concatenation.
                self.flat = nn.Linear(self.spec.entities * (width + 1), d)
                self.operand = nn.Linear(2 * width + len(ACTIONS) + 2, d, bias=False)
                self.second = nn.Linear(d, d)
                self.actor = nn.Linear(d, 1)
                self.value = nn.Linear(d, 1)
            else:
                self.input = nn.Linear(width, d)
                if architecture.kind == 'graph':
                    self.layers = nn.ModuleList(nn.Linear(2*d, d) for _ in range(2))
                elif architecture.kind == 'pooled_mlp':
                    self.layers = nn.ModuleList(nn.Linear(d, d) for _ in range(2))
                else:
                    self.layers = nn.ModuleList(nn.TransformerEncoderLayer(d, 4, dim_feedforward=2*d,
                        dropout=0., activation='gelu', batch_first=True) for _ in range(2))
                self.scorer = nn.Sequential(nn.Linear(3*d + len(ACTIONS) + 2, d), nn.Tanh(), nn.Linear(d, 1))
                self.value = nn.Linear(d, 1)

    def encoder(self):
        if hasattr(self, 'compact_network'):
            from .compact import CompactEncoder
            return CompactEncoder(self.vocabulary, self.architecture, action_policy=self.action_policy)
        return StudyEncoder(self.vocabulary, self.architecture, action_policy=self.action_policy)

    def forward(self, batch):
        if batch.get('feature_identity') != self.feature_identity:
            raise ValueError('Model and study semantics differ')
        if hasattr(self, 'compact_network'):
            return self.compact_network(batch)
        x, present = batch['study_values'], batch['present']
        if self.spec.identities:
            ids = batch['identities']
            embedding = self.content((ids - 1).clamp_min(0)) * (ids > 0).unsqueeze(-1)
            x = torch.cat((x, embedding), -1)
        x = x * present.unsqueeze(-1)
        a = batch['candidates']
        action = torch.nn.functional.one_hot(a[:, :, 0].clamp_min(0), len(ACTIONS)).to(x.dtype)
        exists = (a[:, :, 1:] >= 0).to(x.dtype)
        def operands(values):
            b = torch.arange(len(values), device=values.device)[:, None]
            return [values[b, a[:, :, i].clamp_min(0)] * exists[:, :, i-1:i] for i in (1, 2)]
        if self.architecture.kind == 'flat_mlp':
            base = self.flat(torch.cat((x, present.unsqueeze(-1).to(x.dtype)), -1).flatten(1))
            condition = self.operand(torch.cat((*operands(x), action, exists), -1))
            hidden = torch.tanh(self.second(torch.tanh(base[:, None] + condition)))
            state = torch.tanh(self.second(torch.tanh(base)))
            return self.actor(hidden).squeeze(-1), self.value(state).squeeze(-1)
        h = torch.tanh(self.input(x)) * present.unsqueeze(-1)
        for layer in self.layers:
            if self.architecture.kind == 'graph':
                h = torch.tanh(layer(torch.cat((h, torch.bmm(batch['adjacency'], h)), -1)))
            elif self.architecture.kind == 'pooled_mlp':
                h = torch.tanh(layer(h))
            else:
                h = layer(h, src_key_padding_mask=~present)
            h = h * present.unsqueeze(-1)
        state = h.sum(1) / present.sum(1).clamp_min(1).unsqueeze(-1)
        features = torch.cat((state[:, None].expand(-1, a.shape[1], -1), *operands(h), action, exists), -1)
        return self.scorer(features).squeeze(-1), self.value(state).squeeze(-1)


def parameters(architecture, vocabulary):
    with torch.device('meta'):
        model = StudyActorCritic(vocabulary, architecture, action_policy='commit_decisions_v1')
    embedding = sum(p.numel() for n, p in model.named_parameters() if n.startswith('content.'))
    total = sum(p.numel() for p in model.parameters())
    return dict(total=total, embedding=embedding, trunk=total-embedding, weight_bytes=total*4)


def match_capacity(configurations):
    """Choose every width using exact quadratic parameter counts, no outcomes."""
    choices = []
    for architecture, vocabulary in configurations:
        x = np.array((8., 12., 16.))
        y = np.array([parameters(replace(architecture, hidden_size=int(d)), vocabulary)['total'] for d in x])
        coefficients = np.linalg.solve(np.stack((x*x, x, np.ones(3)), 1), y)
        sizes = range(8, 1025, 4 if architecture.kind == 'attention' else 1)
        choices.append([(int(round(np.polyval(coefficients, d))), d) for d in sizes])
    for target in (250000, 500000, 1000000, 2000000):
        selected = [min(values, key=lambda v: (abs(v[0]-target), v[1])) for values in choices]
        if all(abs(count-target) <= .05*target for count, _ in selected):
            result = []
            for (architecture, vocabulary), (count, d) in zip(configurations, selected):
                architecture = replace(architecture, hidden_size=d)
                actual = parameters(architecture, vocabulary)
                if actual['total'] != count:
                    raise ValueError('Parameter calculation changed')
                result.append((architecture, actual))
            return target, result
    raise ValueError('No common useful capacity within 5% and two million parameters')
