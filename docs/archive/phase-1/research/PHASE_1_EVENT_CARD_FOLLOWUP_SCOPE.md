# Phase 1 event-card Brain/Zen follow-up scope

- Date: 2026-09-06
- Status: proposed; inert gates pass; no target invocation authorized or performed
- Baseline: `920ec84b2eed891c28b5baf7341cefca9287eca6`
- Accepted caller-diagnostic result SHA-256: `e8c6f9aad5035daa21e7329b89669c652c9845ae07049d9f1274b1cd26c762ca`

## Purpose

This disposable metadata-only packet answers two unresolved questions from the
accepted caller diagnostic. It does not add a production policy row.

1. For exact `BrainLeech.ShareKnowledge()`, identify the one key-like string
   that the reviewed straight-line IL window passes through
   `DynamicVarSet.get_Item`, `DynamicVar.get_IntValue`, and then as the count
   argument of `CardFactory.CreateForReward`.
2. For exact `ZenWeaver.EmotionalAwareness()` and
   `ZenWeaver.ArachnidAcupuncture()`, resolve only their
   `AsyncStateMachineAttribute` bodies and retain each complete bounded
   `MoveNext` body after proving exactly one direct call to
   `ZenWeaver.RemoveCardsAndProceed(int,int)`.

The result can support later result-level review of count and completion flow.
It does not prove eligibility, selector readiness, option binding, effect
completion, or production support by itself.

## Exact selection and checks

The canonical selection file has SHA-256
`cf9e66383f9d41b8a061cb3ad8544a2e0b1a4dff43ca0744723962257c0a5a31`.
Target mode pins those bytes before opening the managed image.

The Brain selection binds the exact source
`MegaCrit.Sts2.Core.Models.Events.BrainLeech.ShareKnowledge()` and body
`MegaCrit.Sts2.Core.Models.Events.BrainLeech+<ShareKnowledge>d__9.MoveNext()`.
The tool requires the 13 selected instructions at IL offsets 34 through 78 to
be adjacent decoded instructions with exact opcodes, operands, locals,
constants, and no branch or switch targets. The selected window proves the
following stack flow:

`ldstr(41)` → `DynamicVarSet.get_Item(46)` →
`DynamicVar.get_IntValue(51)` →
`CardFactory.CreateForReward(Player,int,CardCreationOptions)(78)`.

Only the string at offset 41 is revealed, and only if it is 1..96 ASCII
letters, digits, underscores, or dot-separated segments. All Zen user strings
remain the fixed marker `user_string`.

Each Zen source must have exactly one valid `AsyncStateMachineAttribute`, an
exactly resolved nested `ZenWeaver+...MoveNext()` body, and exactly one direct
call to the fixed `RemoveCardsAndProceed(int,int)` callee. The result emits the
two bodies in fixed role order with decoded offsets, numeric opcodes, metadata
identities, numeric constants, local indices, branch targets, and switch
targets. It does not traverse any callees.

Bounds are two emitted bodies, at most 2,500 instructions per decoded body,
5,000 emitted instructions, and 7,500 total instructions including the
non-emitted Brain body. Mismatch and overflow fail closed without partial
semantic output.

## Image and privacy boundary

Target mode accepts only a physical, non-linked `sts2.dll` of exactly
9,363,456 bytes and SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
It verifies stable file size and timestamp around a bounded read, hashes before
`PEReader`, and zeroes the owned image bytes on every post-allocation path. It
never loads or executes the assembly.

The packet reads no resources, localization files, debug data, profile/save,
Cloud, network, or gameplay state. Its one narrowly selected Brain key is a
code literal required to interpret the exact count flow. No other user-string
content is emitted.

## Disposable packet identities

Scanner root: `/private/tmp/event-card-followup-b`.

- `Program.cs`: `e38cecb915ebd91481ba94225d15ebd3930c136e58b225d0f0a55d127168fa93`
- project: `7de08431acf4c02f58898629b6c6e48b300938948a4558b3a6ffd9df9ff01066`
- selection: `cf9e66383f9d41b8a061cb3ad8544a2e0b1a4dff43ca0744723962257c0a5a31`
- fixture runner: `655894f2c6a27e4482bbe011fddd4435ce4c82f8fa5391c622c959e7b0e6422b`
- complete 12-input source manifest:
  `3a5745be55c139af6004d352c352cf8c043bb8feaf859f4ba02ebbc1f39fc370`

The exact reviewed bundle is:

- `EventCardFollowup.dll`, 53,760 bytes:
  `017e87d0bc88dfd4d060c6ddd0193e5ade8ece78e45d0db62d329a39ec6c00e5`
- deps, 421 bytes:
  `1d1df2a47783e7cea5638a49588ff5f7481e10fac62cc3110e2dcdc1819b0b7e`
- runtime config, 257 bytes:
  `9b93bb9ae8b1f2d369e6bfd31f183e2db18031236ff1171bb899522aea902297`
- copied selection, 2,897 bytes: the selection hash above.

## Private bounded capture

The separate wrapper at `/private/tmp/event-card-followup-capture-b` verifies
the complete scanner source manifest and every exact bundle file before
creating an output directory. It drains stdout and stderr concurrently without
stdin for at most 30 seconds, with 2,000,000-byte stdout and 4,096-byte stderr
caps. It kills and reaps on timeout or overflow.

The wrapper creates only a fresh direct
`/private/tmp/event-card-followup-capture-<24hex>` directory at mode `0700`.
After the child is reaped it persists bounded stdout and stderr with `O_EXCL`,
mode `0600`, and `fsync` before checking timeout, overflow, exit status,
stderr, JSON schema, canonical encoding, or semantic counts. A successful
summary is written only after all checks pass. Existing roots and bundle/source
drift fail before target invocation or output creation as applicable.

- wrapper: `9a180da84f686cabd47247021ad8a69d2698b3501a0b6f9864b550fb4c18bac4`
- fixture runner: `14d83758efc113a0828b2be433000cd0bcd08d0c23f0134ce3015048ed4171c5`
- two-input capture manifest:
  `18b76763b7dfc57ef93261ce7510ac7d2b3dd6c708e02efaebc6980343b5619b`

## Stop boundary

The scanner has run only against inert synthetic assemblies. Independent
review must accept this exact scope, source manifests, bundle, and synthetic
record before the coordinator may separately authorize one target invocation.
A failure ends that invocation without a looser retry. The output cannot by
itself authorize a production row, native implementation, live action, or a
broader static read.
