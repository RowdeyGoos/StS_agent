# Current unified release

[bridge.json](bridge.json) is the accepted source, toolchain, test, binary and
package identity for the single production bridge. [validation.json](validation.json)
retains its separately recorded manifest hash, timing and evidence limits.

These are small release records, not source snapshots. Replace them after an
accepted later release; Git keeps earlier versions. The four interim consolidated
release records are preserved at commit `1d63e74`, and original artifact identities
remain in [history](../history/README.md).

The package contains one mod DLL and manifest. Offline tests cover shared-host
handoff/failure behavior, native capabilities, clients, reproducibility and owned
installation/cleanup. They do not establish a live combined-run result. See the
[bridge guide](../../README.md) for the single development and operational workflow.
