# Phase 1 BR0 Static-Audit Scope Deviation

- **Recorded:** 2026-08-29
- **Disposition:** disclosed; no output retained; subsequent inspection
  restricted to exact pinned/disposable paths
- **Affected evidence:** static loader/screen audit only; not the game build,
  profile fixture, or bridge artifact

## What happened

During a delegated read-only search for an already installed managed
decompiler, the agent ran exactly:

```text
rg --files /Users/<operator> 2>/dev/null | rg '/(ilspycmd|ICSharpCode\.Decompiler|Mono\.Cecil|dnlib)(\.dll)?$' | head -n 100
```

Standard output was empty. The first stage nevertheless traversed paths below
the home directory, which was broader than the exact pinned game-assembly
scope. It may have internally enumerated profile-related directory entries.
The file-listing tool may also consult ignore-rule files while walking. It did
not search candidate file contents for the decompiler pattern, no candidate
path passed the output filter, nothing from an ignore file was displayed or
retained, and the command performed no write.

## Containment and claims

The deviation was disclosed immediately. The broad approach was stopped, and
all later audit work used only exact pinned game paths and already-known
disposable probe paths. No profile/save file was intentionally opened, copied,
hashed, parsed, or modified; no game file was edited; and no mod was installed,
loaded, or launched.

This record prevents the static audit from claiming that every metadata lookup
was confined to the intended path allowlist. It does not convert the empty
filtered result into evidence about the presence or absence of any tool or
user-data path.
