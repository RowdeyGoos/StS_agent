# Current validated release records

The [validation summary](validation.json) records the source consolidation and
separately retained hashes of these four successful release manifests. Each
production DLL reproduces its historical accepted bytes. No game was launched.

These files contain identities and test evidence, not source copies. Their
`files` fields identify the exact current source bundle accepted by each live
client. A later code change can be developed and tested normally; retain a new
manifest after its relevant release gate passes. Replace the appropriate current
record and let Git keep previous versions.

Detailed command logs referenced by these records were disposable local outputs.
The original tested release policies, source identities and live evidence remain
available through [history](../history/README.md) and the repository's acceptance
ledgers. A passing fixture is not additional live-game evidence.
