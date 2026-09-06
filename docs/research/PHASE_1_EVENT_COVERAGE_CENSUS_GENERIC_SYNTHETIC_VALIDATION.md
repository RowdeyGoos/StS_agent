# Phase 1 event coverage census generic synthetic validation

- Date: 2026-09-06
- Status: synthetic gate passed; target invocation not performed
- Scope: `PHASE_1_EVENT_COVERAGE_CENSUS_GENERIC_SCOPE.md` SHA-256
  `0f83322a84851242e5bce9d391932182e78419f0777db6044e060404834f4c4e`
- Disposable source manifest SHA-256:
  `25e2e3c64b82b100764b01ec9b1f98b813ed5f25c92455d1089641dbc9e7be8f`

## Invocation and result

The corrected disposable tool was built and exercised with the existing .NET
SDK 9.0.303 and the saved Python 3.11 interpreter. The runner used its fixed
no-package-source NuGet configuration and disposable CLI, package and build
directories. It built and executed inert synthetic managed assemblies only.

Invocation:

```text
<saved-python-3.11> -B -E -s -S run_fixtures.py --dotnet <sdk-9.0.303-dotnet>
```

Exact stdout:

```json
{"schema_version":1,"status":"passed","suite":"event_coverage_census","check_count":12}
```

The process exited zero and emitted no error output.

## Covered boundaries

The new positive case classified exact event, custom and layout ancestry through
generic roots with type-parameter, primitive and array arguments. It verified
four rows and three concrete rows in each category, twelve aggregate rows,
deterministic category/name identities, immediate bases and declared generic
custom interfaces.

The eleven predecessor checks remained passing: exact ordinary classification
and deterministic output; hash-before-PE failure ordering; event overflow; an
external same-name anchor; local base and interface cycles; top-level array and
pinned TypeSpecs; and linked input rejection. The corrected provider therefore
accepts opaque forms only as nested generic arguments and retains the previous
fail-closed treatment when those forms are the ancestry root.

No target assembly path was opened or read, no target assembly was loaded or
executed, and no target census was invoked. No event denominator or additional
runtime capability follows from this synthetic result. Generated build outputs
were removed from the disposable authored-source tree before its 18-file
manifest was created.
