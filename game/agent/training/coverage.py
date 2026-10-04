"""Read-only audits of static content and recorded public model inputs."""
from collections import Counter, defaultdict

from game.agent.contracts import full as f
from .catalog import ENTITY_KINDS, public_catalog


def catalog_coverage(vocabulary):
    """Compare a frozen vocabulary with today's explicit public registries."""
    catalog = public_catalog()
    names = set(vocabulary.names)
    saved = {(e.kind, e.definition_id): e for e in vocabulary.catalog.entries} if vocabulary.catalog else {}
    groups = defaultdict(list)
    for entry in catalog.entries:
        groups[entry.kind].append(entry)
    result = {}
    for kind, entries in sorted(groups.items()):
        missing = [e.definition_id for e in entries if e.definition_id not in names]
        descriptions = Counter(saved[(kind, e.definition_id)].coverage if (kind, e.definition_id) in saved
                               else 'not_bundled' for e in entries)
        result[kind] = dict(total=len(entries), known=len(entries)-len(missing),
                            unknown=len(missing), unknown_ids=missing,
                            bundled_description_coverage=dict(sorted(descriptions.items())))
        if kind == 'relic':
            result[kind]['identity_only_ids'] = [e.definition_id for e in entries
                if (kind, e.definition_id) in saved and saved[kind, e.definition_id].coverage == 'identity']
            result[kind]['no_intrinsic_effect_ids'] = [e.definition_id for e in entries
                if (kind, e.definition_id) in saved and any(
                    field.key.startswith('catalog.effect.') and field.key.endswith('.kind')
                    and field.value == 'no_intrinsic_effect' for field in saved[kind, e.definition_id].fields)]
    return dict(reference_catalog=catalog.identity,
                saved_catalog=vocabulary.catalog.identity if vocabulary.catalog else None,
                vocabulary=vocabulary.identity, vocabulary_size=len(names), by_kind=result,
                identity_coverage_complete=all(v['unknown'] == 0 for v in result.values()),
                interpretation='Known identifiers do not imply learned competence or complete effect descriptions. '
                               'Card mechanics are in the public observation; bundled relic descriptions are partial. '
                               'Static catalogs contain no run outcomes, hidden state or held-out examples.')


class CoverageAudit:
    def __init__(self, vocabulary):
        self.vocabulary = vocabulary
        self.names = set(vocabulary.names)
        self.decisions = 0
        self.entities = Counter()
        self.entity_ids = defaultdict(set)
        self.descriptions = defaultdict(Counter)
        self.saved = {(e.kind, e.definition_id): e for e in vocabulary.catalog.entries} if vocabulary.catalog else {}
        self.unknown = defaultdict(Counter)

    def add(self, decision):
        if type(decision) is not f.PublicDecision:
            raise ValueError('Representation audit requires public decisions')
        f.validate(decision)
        self.decisions += 1
        for root in (decision.run, decision.context):
            for node in f.walk(root):
                if node.kind not in self.names:
                    self.unknown['node_kind'][node.kind] += 1
                if node.kind in ENTITY_KINDS:
                    self.entities[node.kind] += 1
                    self.entity_ids[node.kind].add(node.definition_id)
                    entry = self.saved.get((node.kind, node.definition_id))
                    self.descriptions[node.kind][entry.coverage if entry else 'not_bundled'] += 1
                if node.definition_id not in self.names:
                    category = 'entity_identity' if node.kind in ENTITY_KINDS else 'structural_identity'
                    self.unknown[category][node.kind + '/' + node.definition_id] += 1
                for field in node.fields:
                    if field.key not in self.names:
                        self.unknown['field_key'][field.key] += 1
                    if type(field.value) is str and field.value not in self.names:
                        self.unknown['string_value'][field.key + '=' + field.value] += 1
                for link in node.links:
                    if link.key not in self.names:
                        self.unknown['link_key'][link.key] += 1

    def report(self):
        return dict(schema='sts_representation_coverage_v1', status='complete',
                    catalog=catalog_coverage(self.vocabulary), observed_decisions=self.decisions,
                    observed_entities=dict(sorted(self.entities.items())),
                    observed_unique_identities={k: len(v) for k, v in sorted(self.entity_ids.items())},
                    observed_description_coverage={k: dict(sorted(v.items())) for k, v in sorted(self.descriptions.items())},
                    observed_identity_coverage_complete=not bool(self.unknown.get('entity_identity')),
                    observed_token_coverage_complete=not any(self.unknown.values()),
                    unknown_tokens={key: dict(sorted(values.items())) for key, values in sorted(self.unknown.items())})


def audit_paths(vocabulary, inputs=(), *, split='train', max_decisions=10000):
    """Reuse validated public trajectories; never fit names or restore games."""
    from game.agent.analysis.sources import discover
    from game.agent.recording import load_trajectory
    from game.agent.trace_storage import is_trajectory
    if split not in ('train', 'validation'):
        raise ValueError('Representation audits accept only training/development validation traces, not test')
    if type(max_decisions) is not int or not 1 <= max_decisions <= 1000000:
        raise ValueError('Choose 1–1,000,000 audit decisions')
    audit = CoverageAudit(vocabulary)
    paths = [p for p in discover(inputs) if is_trajectory(p)]
    if inputs and not paths:
        raise ValueError('No public trajectories found in audit inputs')
    sources, seen = [], set()
    for path in paths:
        if audit.decisions >= max_decisions:
            break
        trajectory = load_trajectory(path, split=split)
        if trajectory.sha256 in seen:
            continue
        seen.add(trajectory.sha256)
        count = 0
        for step in trajectory.transitions:
            if audit.decisions >= max_decisions:
                break
            audit.add(step.observation)
            count += 1
        sources.append(dict(path=str(path), sha256=trajectory.sha256, decisions=count,
                            available_decisions=len(trajectory.transitions)))
    result = audit.report()
    result.update(split=split, sources=sources, discovered_trajectories=len(paths),
                  max_decisions=max_decisions,
                  scope='Recorded decision prefixes, capped globally; no gameplay, fitting, or test restoration')
    return result
