# Historical release identities

These are the original manifests for the four selected release compositions and
the general event component, plus their release policies, retained byte-for-byte.
They are evidence and lookup material; the current build and live client do not
read or execute them. Other original files remain in Git.

All 32 retired source trees are available at Git commit
`4f0c9ed912b533da17e431bc2ff59a63b06b2aae`. The [index](index.json) records each
original path, source-manifest hash, contract identity and inventory hash when
that field was recorded by the original manifest. Exact
acceptance results remain in `docs/research/`.

For example, inspect an original file without restoring the old trees:

```bash
git show 4f0c9ed912b533da17e431bc2ff59a63b06b2aae:bridge/Sts2AgentBridge/successors/generic_event_release_v10/check.py
```

Use the same commit in a separate checkout when reproducing a historical build.
Current development belongs in `components/` and `apps/`; retain selected release
packages, commit identities and results instead of permanent source clones.
