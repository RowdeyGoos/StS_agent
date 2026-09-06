# Phase 1 event coverage census result

- Date: 2026-09-06
- Invocation time: 2026-09-06T16:01:25Z (recorded immediately after return)
- Status: stopped fail closed; no event denominator established
- Scope: `PHASE_1_EVENT_COVERAGE_CENSUS_SCOPE.md` SHA-256
  `95612cc3bae166c320ab3988dbe5a7aa56595937b8cbffa27429ee15f3705b5d`

## Reviewed input and tool

The independently accepted tool was invoked exactly once in target mode against
the previously pinned compile/read-only `sts2.dll` image. Before PE parsing the
tool required basename `sts2.dll`, regular non-link shape, size 1..100,000,000,
and fixed SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The previously recorded image size was 9,363,456 bytes. The assembly was read as
data through `PEReader`; it was not loaded or executed.

Exact accepted tool identities:

- `Program.cs`: `bba9b372c6f911e944aa57c7a8ff0bd7132acb2bf6666761ae64ac3430be0b1b`;
- `EventCensus.csproj`: `14c2b17719a82cc63e0bbcb76760ff5af20b710ab3f295b5ae825c1f7b3d4adc`;
- `NuGet.Config`: `5256a7e3e07d2c5c94f7a1e6c45f39aab011c659c5e2d53e452dea525ce04575`;
- `run_fixtures.py`: `2b6e91bda6ae535c07593ff12dc50da643aaf64373b34490bf0ceac3c390b034`;
- disposable source manifest:
  `d14e9fa142843840ae419782b8093c8e51f50f4cd9396116b195e66392ab8ab1`.

The inert synthetic gate passed all 11 accepted checks immediately before the
target invocation:

```json
{"schema_version":1,"status":"passed","suite":"event_coverage_census","check_count":11}
```

## Exact sanitized result

The process exited 1 and emitted no stdout. Its complete stderr was:

```json
{"schema_version":1,"status":"failed","error":"ambiguous_ancestry"}
```

The canonical line including its trailing LF is 68 bytes with SHA-256
`7a1952646dd361ff769dff8cd49ea34405aaee68aff30fd04227dedd3ce745f5`.

The tool emitted no category row, event/type name, count, method signature, IL,
resource, localization value, path, or exception detail. No second target
invocation was made. The reviewed scope explicitly requires an ancestry failure
to end this census packet without a looser rerun.

## Disposition and coverage matrix

The pinned-build denominator for concrete event models remains unknown. No event,
custom-node, or layout count can be claimed from this attempt. The failure code
does not distinguish a cycle, unresolved same-module relation, external
same-name anchor, or unsupported ancestry TypeSpec, so this result does not
classify the underlying metadata shape.

Repository/static evidence remains unchanged:

| Interaction family | Implemented evidence before census | Census effect |
| --- | --- | --- |
| ordinary event choices and final Proceed/map | accepted bounded event controller | unchanged |
| one item reward child | accepted exact item session/broker path | unchanged |
| RoomFullOfCheese/Gorge add exactly 2 of 8 | accepted completion-fixed card child facts | unchanged |
| remove/transform/other upgrade or add cardinalities | pure core only or unbound target APIs | still unsupported |
| embedded event combat | lifecycle method names only; no accepted controller | still unsupported |
| custom event nodes/layouts | interface/layout anchors only | still unsupported |
| all concrete events | no finite denominator | unresolved |

The event-orchestrator first slice may continue only from the already accepted
ordinary/item/Cheese facts. This stopped census adds no native caller, event ID,
policy, capability, live readiness, or permission for a member/IL follow-up.
