# Phase 1 event coverage census generic-ancestry correction scope

- Date: 2026-09-06
- Status: proposed; independently review before any target invocation
- Predecessor result: `PHASE_1_EVENT_COVERAGE_CENSUS_RESULT.md`
- Evidence boundary: reviewed source, the predecessor's sanitized fixed failure,
  and disposable synthetic managed assemblies only

## Reason for the correction

The first target census stopped with only `ambiguous_ancestry`; it emitted no
row, type, count, signature, IL, resource, path or exception detail. That result
cannot identify which target relationship caused the stop.

Source review found a deterministic false-positive class in the accepted tool.
`RootTypeProvider.GetGenericInstantiation` returned the named generic root, but
`DecodeSignature` first decoded every generic argument. The provider threw for
generic type parameters, primitive types and array types, so normal metadata such
as `Base<T>`, `IMarker<T>`, `Base<int>` or `Base<int[]>` stopped the complete graph
before the generic root could be used. The correction addresses that ordinary
metadata form; it does not infer that any particular target type triggered the
first failure.

## Exact corrected tool

The disposable source root is `/private/tmp/event-census-generic-a`. It is a
copy of the accepted census tool with one bounded ancestry correction and one
new synthetic fixture family. Its fixed pinned target identity, file-shape and
link checks, 100,000,000-byte input ceiling, image zeroing, metadata-only
`PEReader` use, three exact local anchors, row/count ceilings and fixed output
schemas are unchanged.

Exact identities:

- `Program.cs`: `1646708470b6de9ef7150b9b5a258c30fcfaf24c565904a585715db08a5812ce`;
- `EventCensus.csproj`: `14c2b17719a82cc63e0bbcb76760ff5af20b710ab3f295b5ae825c1f7b3d4adc`;
- `NuGet.Config`: `5256a7e3e07d2c5c94f7a1e6c45f39aab011c659c5e2d53e452dea525ce04575`;
- `run_fixtures.py`: `7f406ddd0aade2cd6eb332f0afaba54076bfd412c79a930e6d1b406a2a8e9886`;
- `synthetic/generic/Fixture.csproj`:
  `9cc75ce6070defdad23dc17bbb3b2f94d112c6800d3d4d4feb2bcdd70975ffce`;
- `synthetic/generic/Types.cs`:
  `c410831ff61a2813403643bebfcdcb12676fa84d37065ab07d0822ce95a53269`;
- 18-file disposable source manifest `source_manifest.json`:
  `25e2e3c64b82b100764b01ec9b1f98b813ed5f25c92455d1089641dbc9e7be8f`.

The manifest lists every authored tool and synthetic-fixture input and excludes
the manifest itself and all build, package, CLI and generated output directories.

## Corrected ancestry rule

Signature decoding now distinguishes a named ancestry root from an opaque type
argument. A generic instantiation is accepted only when its generic root decodes
to a `TypeDefinition` or `TypeReference`; its arguments do not participate in
ancestry identity. Generic parameters, primitives, arrays, modifiers, pinned,
by-reference, pointer and function-pointer shapes decode to an opaque nil value.

An opaque value is harmless when nested as a generic argument. If that value is
the top-level base or interface TypeSpec, the existing graph traversal still
fails with `ambiguous_ancestry`. This retains the accepted top-level array and
pinned TypeSpec stop boundary and does not unwrap modifiers or accept a generic
root that is itself opaque.

## Synthetic gate

The prior eleven checks remain unchanged. A twelfth fixture compiles only inert
types and proves all three category traversals through generic bases/interfaces
whose arguments are a type parameter, `int` and `int[]`. It checks exact counts,
concrete counts, the twelve expected category/name pairs, their immediate base
names and the generic custom base's declared interface names.

The unchanged negative fixtures still require fixed rejection for external
same-name ancestry, local base and interface cycles, top-level array TypeSpec,
top-level pinned TypeSpec, row overflow, malformed image and symlink input.

The accepted synthetic invocation shape is:

```text
<saved-python> -B -E -s -S run_fixtures.py --dotnet <sdk-9.0.303-dotnet>
```

Expected output is exactly:

```json
{"schema_version":1,"status":"passed","suite":"event_coverage_census","check_count":12}
```

## Stop boundary

This scope does not authorize a target invocation. After independent review of
this document, exact sources and synthetic result, the coordinator may prepare
one separate exact authorization for the same pinned metadata-only target
census. A failure again ends that invocation without a looser retry. No method
body, member, resource, localization, profile/save, Cloud, gameplay, native
execution or network access is included.
