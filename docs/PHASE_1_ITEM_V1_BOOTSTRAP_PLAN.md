# Item V1 secure operator and bootstrap packet

- Date: 2026-09-05. Baseline `2301e23`, selected 23cf integration checkout.
- State: implemented, independently accepted, and source-frozen.
- Authority: continued bounded development/testing. Repository, disposable synthetic filesystem, and compile-only target references; no live setup.

## Outcome and boundaries

Create sibling `bridge/Sts2AgentBridge/successors/item_bootstrap_v1`. Connect the frozen item implementation to secure operator files and a first-ProcessFrame startup, then compile a separately named single-assembly candidate. Preserve every byte of old 0.8.0 and all three frozen successor trees and their inventories. This packet changes no item semantics, action count, route, credential format, transport limit or uncertainty rule.

This is an install-free bootstrap candidate gate. A successor default-deny whole-assembly surface policy and its negative fixtures, canonical release package, item-aware operator/installer/cleanup tooling and campaign preflight are still required before any live load. Compile success is not permission to install. No real home/operator tree is read by tests; no production entrypoint, target assembly, native item adapter or build guard is executed. No production port or socket is used in this packet. No profile/save/Cloud access, target-method discovery, retained live corpus, old action retry, remote Git or broader game capability.

Ownership: operator lane owns `operator/` and `operator_tests/`; bootstrap lane owns `lifecycle/`, `lifecycle_tests/` and `native/`; coordinator owns this plan/shared docs, `Directory.Build.props`, `production/`, `check.py` and `source_identity.json`. Independent review owns no implementation. Shared APIs below freeze before writers start.

## Fixed operator scope and ownership

Production entrypoint is internal `ItemOperatorFiles.OpenEnabled()`, with no arguments. It returns nullable `ItemOperatorConfiguration`, an IDisposable lease, only for the byte-exact enabled transport config. Namespace `Sts2AgentBridge.Successors.ItemBootstrapV1` is shared by new types. Missing, disabled, invalid, unsafe or unsupported input returns null, with no exception/path/data logging. It creates no credential, build check, Godot reference/callback, adapter, runtime, nonce or listener.

The only operator path is the OS-account home followed by exact components `Library/Application Support/Sts2AgentBridge/item_v1/config.json` and `credential.hex`. No environment/current-directory/path parameter fallback, search, enumeration, creation, repair or mutation. Configuration bytes are exactly the two documents frozen by the transport plan, no newline; at most512 bytes. Old r0a path/schema/token is never consulted.

Lease API:
- `byte[]? TakeConfiguration()`: transfers its exact enabled mutable array once; caller owns zeroing if runtime never takes it.
- `byte[]? ReadCredentialOnce()`: reserves once before any attempt, reads only the fixed leaf relative to its retained validated item directory, returns exact64 lowercase-hex ASCII mutable bytes or null. Never retries; returned buffer transfers to the caller.
- `Dispose()`: idempotently zeros any untransferred config and closes every owned descriptor. Taking config does not close the directory until the credential attempt/Dispose.
The lease retains the directory chain and config descriptor until it is disposed. Before the credential read, revalidate their owner/mode/type/ACL and descriptor-to-parent-name identity, and require unchanged config identity/metadata. A renamed or replaced component cannot redirect the read. Internal ordinary failures return null after cleanup. No credential string, immutable copy, hash or fingerprint.

## Descriptor backend and platform boundary

Use only macOS arm64; reject unsupported OS/architecture and unequal real/effective UID before filesystem/account access. Resolve home from effective UID via one bounded `getpwuid_r` buffer of16384 bytes. Require result to equal the supplied passwd storage, returned UID to equal effective UID, and pw_dir to lie inside the owned scratch buffer with a NUL terminator inside both that buffer and the1024-byte bound. Interpret only UID/home fields; use strict UTF-8 decoding without replacement and zero/free the scratch buffer. Reject errors/ERANGE; no growth/retry or alternate lookup. Home must be canonical absolute lexical components (no empty, dot, dot-dot, NUL, newline or carriage return), at most1024 UTF-8 bytes and32 components, each at most255 bytes.

Read-only interop is a narrowly scoped infrastructure exception in this new candidate, not a change to the old bridge policy. Native module is exactly `/usr/lib/libSystem.B.dylib`. Allowed entrypoints only: `getuid`, `geteuid`, `getpwuid_r`, `open`, `openat`, `fstat`, `fstatat`, `read`, `close`, `acl_get_fd_np`, `acl_get_entry`, `acl_get_tag_type`, `acl_free`. No dynamic library loading, arbitrary symbol resolution, process execution, writes or other native calls. Default Cdecl and exact arm64 signatures/layouts are validated by a disposable C ABI probe against local SDK headers before freeze. No unsafe C# blocks. Native pointer storage is confined to this backend.

Open slash once, then every home/fixed directory as one component via openat with `O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_DIRECTORY`; open leaves with `O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK`. No write flag. Hold descriptors for the chain and close them once in reverse order. Use fstat on each descriptor and fstatat(parent,name,AT_SYMLINK_NOFOLLOW) to bind it to its named parent; recheck after leaf reads and before lease handoff/credential access.

Root and home ancestors must be directories owned by root or effective UID with no group/other write. Home, Library and Application Support must be effective-UID-owned directories with no group/other write. Sts2AgentBridge and item_v1 must be exact mode0700 and effective-UID-owned. Files must be regular, effective-UID-owned, exact mode0600 and link count1. Reject special bits. Inspect ACLs by descriptor on the full chain/leaves; at most169 entries, permit only tag ACL_EXTENDED_DENY (2), reject ACL_EXTENDED_ALLOW (1), unknown tags, ambiguous iteration/errors, or a170th entry; free every ACL allocation. No qualifier/permission/flag-shape claim is made. A deny tag cannot grant access. This permits ordinary macOS deny-delete ACLs without silently accepting grants.

Configuration length1..512 and credential length64 are checked before read; read into bounded mutable scratch, require exact length and EOF, compare same-descriptor pre/post dev/ino/type/mode/uid/nlink/size/mtime/ctime and parent-name identity; reject change/truncation/growth/overflow. EINTR may retry at most8 times per native operation/read phase; other errors fail closed. Zero every untransferred array and read scratch on every exit. File descriptor close is attempted once; never retry close on EINTR and risk closing a recycled descriptor. Cleanup must attempt all remaining descriptors even if one close/free fails; any close/acl_free failure makes an otherwise successful operation fail closed.

Residual: descriptor binding prevents pathname substitution and symlink redirection. It is not immunity against a hostile process with the same UID mutating the same inode or process memory.

A production-internal `ItemPinnedFileIdentity.Verify(string assemblyPath, long expectedLength, string expectedSha256)` may use the same descriptor backend solely from the pinned build guard. It accepts only one of the two frozen (basename,length,hash) tuples: sts2.dll/9363456/e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18; GodotSharp.dll/5613568/0e4897ecdfb31456a97c7d8028dfb8d7dbdc632e2f73fc9b438d7b266a139289. Path must originate at exactly typeof(MegaCrit.Sts2.Core.Modding.ModInitializerAttribute).Assembly.Location for sts2 and typeof(Godot.GodotObject).Assembly.Location for GodotSharp. This proves the descriptor-bound current file identity at Location; it does not certify the already mapped in-memory image. Open from slash with the same no-link descriptor walk; root/effective owner, no group/other write, regular leaf/linkcount1, a fixed64KiB SHA256 streaming buffer with the exact tuple file length, exact EOF and stable identity. This method never returns contents/digest or permits arbitrary expected identity. It is not run against game files in this packet.

## Bootstrap and frame lifecycle

Production assembly name/ID is `Sts2AgentBridgeItemV1`, version1.0.0 (all four version fields fixed, no Git revision). Its only initializer is a new ModInitializer("Initialize") static entrypoint calling the new bootstrap. No old bootstrap/logger/service or incompatible-locked fallback is included.

Initialization is one-shot for process lifetime, including failure, stop or incomplete cleanup. Order: reserve once; OpenEnabled config lease; exact pinned build guard pass; ReadCredentialOnce; TakeConfiguration and close lease; attach one stored SceneTree.ProcessFrame Callable; on the first actual frame construct adapter and call frozen runtime Create, then Start once. This order means missing/disabled/invalid configuration never accesses build/Godot/credentials. Invalid credentials never attach or construct adapter/runtime. Build guard requires macOS arm64 and both exact loaded assembly tuple checks; uncertainty/mismatch never starts a listener.

The frame callback witnesses ownership. Initializer thread affinity is unproven. Reuse of the previously exercised attachment seam supports attachment viability; only the first callback establishes runtime ownership. Use only already accepted Godot APIs Engine.GetMainLoop, SceneTree.Connect(ProcessFrame,stored Callable,0), Callable.From and Disconnect. Production adapter is constructed only on first frame. First frame captures Environment.CurrentManagedThreadId and creates runtime on that same thread; later frames only drain that same runtime, with no re-creation, reload, reset or nonce replacement. Wrong-thread frame calls request the non-Godot stop path and cannot detach or dispatch. Hook removal must return truthfully: an exception retains attachment ownership and can be tried on a later owner frame.

Use a pure `ItemBootstrapLifecycle` behind internal injected frame/runtime/factory interfaces, with actual production wrappers separately compiled. Bootstrap owns config/credential arrays until transfer exactly once into frozen Create. Before transfer, every build/attach/startup/stop/race failure zeros them; after transfer frozen Create/runtime own them. No credential/body/exception logging. No success/failure HTTP body is synthesized by bootstrap.

Capture a monotonic five-second deadline immediately when credential bytes transfer from the lease, and arm a stored timer before attachment for the remaining duration. Timer scheduling cannot promise zeroing at an exact wall-clock instant: it requests stop/zero at or after the deadline. Every first-frame path checks the deadline before adapter/runtime creation, so delayed timer delivery never permits late activation. Timer and AppDomain.ProcessExit handlers invoke the same bounded stop request; neither calls Godot Disconnect. Cancel/dispose the timer on activation/stop. Atomically transfer both buffers under a short lock to exactly one owner: stop either takes/zeros them or observes a transfer.

First-frame factory/Create/Start is an explicit startup participant. No lock is held across factory/Create/Start or StopAndJoin. Stop cannot classify an absent runtime as fully stopped or detach while startup is in flight. Publish the newly created runtime under the gate before calling Start outside the gate, and recheck stop before Start. If stopped after Create and before Start, skip Start and StopAndJoin that same runtime. Races inside Start are handled by the frozen runtime; never create a replacement. The production factory accepts the exact configuration/credential arrays, constructs the native adapter on the owner frame, and calls frozen Create once. On invoking Create it transfers both arrays; before invocation it must zero them if adapter construction fails. The pure runtime interface contains only Start, DrainFrame, StopAndJoin and IsStopped.

Stop requests reject further start/drain, call runtime StopAndJoin with its frozen2-second budget, and preserve false/incomplete state. Runtime stop precedes any frame disconnect. Off-thread ProcessExit/timer never call Godot Disconnect and never report full stopped/detached; retain host/callback until an owner-frame cleanup or process termination. On a later owner frame, IsStopped permits deferred detach; no repeat runtime factory/Start/POST. Full stopped is true only after runtime teardown (or no runtime) plus attachment absent or successfully owner-frame detached, and pending buffer/timer cleanup. Do not promise hot unload or a game unload callback; none is evidenced. The process-exit hook is new, not inherited from the old bootstrap.

The pure API/details may be private to the bootstrap lane except the public frozen ItemTransportRuntime calls and operator APIs above. Tests inject fake build/config/frame/runtime collaborators without target/Godot dependencies and prove exact ordering and byte ownership. They must execute the production lifecycle code, not a mirror.

## Tests and reproducible compile gate

Test-only synthetic root/native hooks are compiled only with `ITEM_BOOTSTRAP_TEST_SEAM`, never shipped. They accept only new owned disposable roots under physical /private/tmp; the production path has no override. Synthetic fixture traversal may start at a supplied opened fixture-home descriptor to avoid treating world-writable /private/tmp as a production home ancestor. Pure fake metadata covers slash/home-ancestor rejection. Actual libc tests run on the same selected backend, only against fixture files. No production OpenEnabled/account-home lookup is invoked.

Operator tests cover native ABI/layout, exact config/credential, missing/disabled/invalid/old documents stopping early, ownership/mode/ACL/link/symlink/nonregular/size errors, descriptor/name replacement, read mutation, EINTR bounds, close failures, complete descriptor cleanup and zero ownership. Actual FIFO fixtures are nonblocking. Grant and deny ACL fixtures are confined to disposable files. Wrong-owner/forced-failure cases may use pure facts/injected syscall results rather than privileged filesystem changes.

Lifecycle tests cover missing config/build mismatch/invalid credential, stored frame attachment, first-frame-only creation and owner identity, wrong thread, one-shot/reentrancy, attach/factory/Start failures, expiry, ProcessExit races, stop during startup/frame work, false bounded join followed by deferred completion, disconnect failure, no retry/replacement and byte cleanup. Fake runtime Start binds no sockets. Pure test dependency inventories must exclude sts2/Godot before execution.

Coordinator checker verifies a frozen new source inventory plus all three exact successor manifests/inventories and old48. It snapshots verified sources into a new physical /private/tmp root, uses pinned SDK9.0.303 with isolated CLI/artifacts/NuGet and offline sources/auditing disabled, then executes pure lifecycle and synthetic operator tests. It compiles production against only the two known size/hash-pinned compile references, never loads it. Production explicit Compile links only core3, wire3, transport6 (excluding test AssemblyInfo) and native1 frozen source files plus new operator/lifecycle/native sources. No ProjectReference, old assembly, implicit compile, test seam, runtime dependency DLL, PDB or PCK. Compare two fresh production DLL builds and record exact source/reference/artifact identities. No release ZIP or live-ready claim before the separate surface/package gates.

## Freeze acceptance

Independent review accepted the semantic packet at SHA-256 `77c2f48e8851548dd1212fa93ab2d9a205f38ea78a2db71380cf19b0904b5d0a`. Only the status line, this acceptance note and the appended reviewed clarifications/implementation disposition changed after freeze. Operator and bootstrap implementation ownership is complete; the accepted source inventory is frozen. No live gate is selected.

## ABI appendix

Local SDK26.5 headers and a disposable arm64 C compile/read probe establish these facts. Native module /usr/lib/libSystem.B.dylib; plain fstat/fstatat symbols (no $INODE64 suffix on arm64); Cdecl. struct stat is144 bytes/alignment8: dev0 (int32), mode4 (uint16), nlink6 (uint16), ino8 (uint64), uid16/gid20 (uint32), rdev24 (int32), atime32/mtime48/ctime64/birthtime80 (each two signed64-bit seconds/nanoseconds), size96/blocks104 (int64), blksize112 (int32), flags116/gen120 (uint32), lspare124 (int32), qspare128 (two int64). struct passwd is72 bytes/alignment8: pointer fields name0/password8/class32/gecos40/dir48/shell56; UID16/GID20 uint32, change24/expire64 signed64. Only UID/home are interpreted.

O_RDONLY0, O_NONBLOCK0x4, O_NOFOLLOW0x100, O_DIRECTORY0x100000, O_CLOEXEC0x1000000; AT_SYMLINK_NOFOLLOW0x20; kind mask0xf000, directory0x4000, regular0x8000. EINTR4, ERANGE34, ENOENT2, EINVAL22. getpwuid_r returns its error number directly. ACL type0x100, FIRST0/NEXT-1, allow1/deny2. acl_get_fd_np NULL plus ENOENT means no extended ACL; any other null/error fails. acl_get_entry returns0 with nonnull entry on success, and -1/EINVAL means end; every other result fails.169 is the deliberately finite on-disk-format ceiling, despite the SDK ACL_MAX_ENTRIES macro being128. After169 accepted entries, one additional NEXT must return exactly end. close is never retried. ABI probe source SHA2563d9339bf3f6cfd4f1966d86c064c2d9ed1b97c9868575072e91f4eeea4023df0; it executed only on an owned disposable synthetic file, with no account-home lookup.

Synthetic test code may invoke /bin/chmod with exact +a/-a ACL arguments only against its own fixed allowlisted disposable file, or use injected native results. These mutation primitives never ship in production.

## Reviewed implementation clarifications

Independent review accepted two bounded clarifications while preserving the
semantic freeze. The actual FIFO fixture may use /usr/bin/mkfifo with argument
list `-m 600 <fresh fixed fixture-root>/fifo`, no shell, discarded redirected
output, bounded wait and kill/reap on failure. This setup is test-only and adds
no production primitive.

The explicit frozen transport source links retain exactly two internal
instance bool StartForTests overloads, accepting TcpListener and
TcpListener/Action. The candidate metadata gate binds/counts those signatures
and rejects new bootstrap test/synthetic hooks; the friend-test AssemblyInfo
is excluded. Candidate metadata does not prove inherited internals, including
the endpoint predicate, unreachable from production call sites. That proof
belongs to the pending whole-assembly surface policy.

## Implementation disposition

This packet is implemented and independently accepted. The
[acceptance ledger](research/PHASE_1_MISSING_ROOM_ACCEPTANCE.md) records its
20-input inventory, 13 actual-backend operator groups, 24 lifecycle groups,
24 independent checker cases and two identical fresh candidate builds.
Preserve every authored byte in this fourth successor tree. The product is
one install-free Sts2AgentBridgeItemV1.dll; whole-assembly surface acceptance,
canonical release packaging, item-aware operational tools and live testing
remain separate gates. No game setup is needed yet.
