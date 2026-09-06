# Phase 1 event card preview candidate synthetic validation

- Date: 2026-09-06
- Status: synthetic gate passed; target invocation not performed
- Scope: `PHASE_1_EVENT_CARD_PREVIEW_SCOPE.md` SHA-256
  `3546c522bcbce17dfdcb18daca8dd1531514f6c5b1f87a28d38368f5e3a88bb7`
- Disposable source manifest SHA-256:
  `57a66b5d69c19c2c01aadff7c71dcca1fd3b9972a9f14687c6a9ca0aab93972e`

## Invocation and exact result

The disposable tool and two inert fixture assemblies were restored and built
offline with the existing .NET SDK 9.0.303, cleared package sources,
single-node restore/build, disabled shared compilation, and disposable
CLI/package/artifact directories.

Invocation:

```text
<saved-python-3.11> -B -I -S run_fixtures.py --dotnet <sdk-9.0.303-dotnet>
```

Exact stdout:

```json
{"schema_version":1,"status":"passed","suite":"event_card_preview","check_count":21}
```

The process exited zero and the runner rejected unexpected build/tool stderr.

## Covered boundaries

The positive fixture emits bounded candidates for direct, inherited, explicit
`MethodImpl`, default-interface, private-shadow, and public-`new`-shadow
implementers. The public-shadow case proves the tool does not mistake a nearer
same-name method for the CLR interface target: both derived and inherited
candidates remain visible and no resolved implementation is claimed. Metadata
tokens preserve distinct method and mapping rows; textual identity collisions
fail closed in the tool.

The gate checks the bodyless exact interface declaration, method flags and
signatures, exact `MethodImpl` rows, all fixed body roles, clone-origin field
flow, `CloneCard` candidates calling `CreateClone`, `NCardHolder.CardModel`
returning the card node model, and `NPreviewCardHolder` inheriting
`NCardHolder`. A repeat proves byte-identical canonical output.

Negative cases cover a wrong image hash, more than 32 concrete implementers, a
linked input, a relative path, an actual FIFO rejected before blocking, a
malformed managed image, and target mode with the wrong exact size. Wrapper
fixtures cover create-only output roots, linked-bundle rejection, bounded
kill/reap on output overflow, and private stdout/stderr retention for both a
nonzero/stderr failure and a zero-exit malformed-schema failure. Successful and
failed raw files are mode `0600`; no failure emits a public summary.

The release tool was built in two separate roots. DLL, deps and runtimeconfig
bytes matched exactly. Generated build and fixture outputs were removed after
the gate; only the separately pinned three-file bundle remains next to the
authored source packet.

No target path was opened or read, no target assembly was loaded or executed,
and no production adapter or caller row was created. This result validates only
the finite candidate selector and its failure bounds. It does not establish an
actual target interface implementation or authorize runtime use of `CloneOf`.
