# Phase 1 event-card Brain/Zen follow-up synthetic validation

- Date: 2026-09-06
- Status: passed against inert synthetic managed assemblies only
- Scope: `PHASE_1_EVENT_CARD_FOLLOWUP_SCOPE.md`

The disposable scanner built with SDK 9.0.303 with zero warnings and zero
errors. Its fixture gate passed exactly 15 checks:

- exact output schema, image/config/prior hashes, and count consistency;
- exact one-key Brain flow and two ordered Zen bodies;
- exactly one direct `RemoveCardsAndProceed(int,int)` call in each Zen body;
- all emitted Zen user strings redacted;
- byte-identical repeated output;
- wrong image digest rejection;
- Brain window-offset drift rejection;
- Zen callee drift rejection;
- duplicate Zen call rejection;
- missing async state-machine rejection;
- linked input rejection;
- noncanonical selection rejection; and
- target-mode config drift rejection before an absent target path is opened.

Canonical scanner result:

```json
{"schema_version":1,"status":"passed","suite":"event_card_brain_zen_followup","check_count":15}
```

The capture fixture passed exactly four checks. It validates a complete
successful private capture and file modes, rejects output-directory reuse,
persists a scanner failure before validation without writing a summary, and
rejects a same-size bundle digest mutation before output creation.

Canonical capture result:

```json
{"schema_version":1,"status":"passed","suite":"event_card_brain_zen_followup_capture","check_count":4}
```

The scanner source manifest SHA-256 is
`3a5745be55c139af6004d352c352cf8c043bb8feaf859f4ba02ebbc1f39fc370`.
The capture source manifest SHA-256 is
`18b76763b7dfc57ef93261ce7510ac7d2b3dd6c708e02efaebc6980343b5619b`.
No target image, live process, profile, save, Cloud, network, or gameplay state
was read or invoked by these checks.
