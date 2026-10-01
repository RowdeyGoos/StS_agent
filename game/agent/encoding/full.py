"""Version 2 vocabulary over the same lossless public tensor machinery."""
from dataclasses import dataclass
import re

from game.agent.contracts import full
from .codec import PublicEncoder
from .schema import EncodingProfile


@dataclass(frozen=True, slots=True)
class FullRunProfile(EncodingProfile):
    nodes: int = 131072
    references: int = 16384
    strings: int = 4096
    string_bytes: int = 256
    candidates: int = 2048

    @property
    def layout(self):
        return (2, self.nodes, self.references, self.strings, self.string_bytes, self.candidates)

    @property
    def identity(self):
        return 'sts_public_graph_v2:' + ':'.join(map(str, self.layout[1:]))


FULL_RUN_PROFILE = FullRunProfile()


class FullRunEncoder(PublicEncoder):
    contract = full
    expected_format = 2
    tree_depth = 64
    fields = ('run', 'context', 'kind', 'definition_id', 'ref', 'fields', 'key',
              'value', 'links', 'targets', 'children')
    actions = full.ACTIONS
    namespaces = full.NAMESPACES
    reference_pattern = re.compile(r'(' + '|'.join(full.NAMESPACES) + r'):[0-9]+\Z')
    decision_schema = full.SCHEMA
    decision_profile = full.PROFILE

    def __init__(self, profile=FULL_RUN_PROFILE):
        if not isinstance(profile, FullRunProfile):
            raise TypeError('FullRunEncoder requires a version 2 profile')
        super().__init__(profile)

    def _ready_wire(self, decision):
        # V2 to_dict already checks every readiness invariant, including legal
        # candidates. V1 separately checks availability and keeps its own path.
        return self.contract.to_dict(decision)

    def _pack(self, decision, wire, *, record_types=()):
        if (type(decision) is full.PublicDecision and
                record_types == (full.Node, full.Field, full.Link) and
                self.fields == FullRunEncoder.fields):
            from .full_records import pack_records
            return pack_records(self, decision)
        return super()._pack(decision, wire, record_types=record_types)

    def _pack_prepared(self, decision, prepared):
        if type(prepared) is not full.PreparedPublic:
            raise full.ContractError('Expected a prepared public observation')
        prepared.require(decision)
        # Preparation owns canonical immutable records. Traverse those records
        # directly; a mutable wire copy is only needed by consumers that own it.
        roots = None if isinstance(decision, full.RunOutcome) else {
            'run': decision.run, 'context': decision.context}
        return self._pack(decision, roots, record_types=(full.Node, full.Field, full.Link))

    def encode_prepared(self, decision, prepared):
        if type(prepared) is not full.PreparedPublic:
            raise full.ContractError('Expected a prepared public observation')
        prepared.require(decision)
        # Custom encoders retain their encode/pack/_ready_wire hooks and full
        # validation. Only the exact built-in encoder opts into this reuse.
        if type(self) is not FullRunEncoder:
            return self.encode(decision)
        return self._pad(self._pack_prepared(decision, prepared))
