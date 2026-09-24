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
