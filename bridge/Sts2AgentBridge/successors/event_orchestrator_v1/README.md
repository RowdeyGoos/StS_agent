# Shared event controller v1

Functional successor toward broader event coverage. It is not an installable
release and does not add a listener, bootstrap, campaign or live endpoint.

The event parent owns option decisions and final Proceed. It admits a typed item
or card child only after the option that opened it has an accepted receipt. The
child completes through the actual frozen item/card session; its resolved payload
is delivered before the parent consumes it and resumes. Each episode is tied to
its parent action, policy, factory and foreground screen. Old screens and used
options cannot be reused as fresh decisions.

The initial native scope is ordinary event choices, the existing item reward
surface and Room Full of Cheese's exact GORGE add-two-of-eight selector. Other
card callers, custom event layouts, embedded combat, repeated stable-key loops
and broader reward types remain unsupported. Generic card core operations do
not imply native support for every event that uses them. The repository coverage
plan and census result record the separate all-events objective and current gaps.

The injected Python entry point is
`run_event(request, *, provider, clock=time.monotonic, sleep=time.sleep)`.
The request callback accepts `(method, route, bytearray | None)` and returns an
owned mutable response buffer. The host clears mutable request/response buffers
after consumption. `provider(DecisionView)` receives a deeply immutable parent,
item or card decision and returns one advertised action ID. `first_legal` is an
explicit deterministic fixture provider. It is not a strategic event policy.

One event shares a 30-second monotonic budget, 2,048 reads, 12 parent actions,
four child episodes and 52 total actions. Item/card per-child limits remain
unchanged. There is no retry after a failed or uncertain action. The sanitized
summary distinguishes ordinary option transitions, completed child episodes,
child effect reconciliation and the final map handoff; ordinary HP/gold effects
are not independently verified.

`check.py` verifies all twelve frozen predecessor identities and the original
48-file bridge, explicit project closure, synthetic sessions and actual-adapter
fixtures, the actual C# to Python composition, and two matching native builds.
Only pure fixture executables run; pinned target assemblies are compile inputs.
`--unfrozen` is an explicitly unaccepted candidate check before the first source
freeze. `freeze_sources.py` creates the initial manifest once and refuses any
replacement. A source freeze alone does not constitute acceptance or live readiness.

Acceptance is recorded in the repository's event-orchestrator acceptance ledger.
No profile/save access, Steam Cloud changes, retained live corpus or remote Git
operations are part of this component.
