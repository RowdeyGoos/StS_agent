# Game Build Manifests

This directory contains immutable, sanitized identities for game installations
used by the full-game program. A new upstream build gets a new file; an existing
capture is never silently updated to point at different binaries.

The manifests contain project-authored metadata, public storefront identifiers,
file sizes, and cryptographic hashes. They do not contain game binaries,
assemblies, assets, raw Steam manifests, saves, account identifiers, absolute
user paths, or extracted proprietary content.

## Status boundaries

A build manifest proves only the installed binary identity that it names. It
does not by itself prove:

- which player profile or unlock state is active;
- which Workshop items or local mods are enabled;
- which bridge is selected or safe;
- simulator fidelity or content coverage;
- campaign readiness or reproducibility of an unavailable old depot.

Those requirements remain separate fields and gates in the Phase 0 charter and
Phase 1 integration evidence plan.

## Integrity

Each file has two relevant fingerprints:

1. `identity.installation_tree.sha256` fingerprints all regular files in the
   Steam installation root using sorted install-relative paths and SHA-256 file
   hashes.
2. `integrity.identity_payload_sha256` fingerprints the stable `identity`
   object. Capture time, host OS, repository dirtiness, and open work are kept
   outside that payload, so repeating a capture of the same build produces the
   same identity.

The canonical identity hash is recomputed with:

```bash
jq -cSj '.identity' manifests/game-builds/<manifest>.json | shasum -a 256
```

The recorded hash must match the first field of that output. JSON files use
sorted keys only for hashing; human-readable key order is chosen for clarity.

`identity.installation_tree` is the clean **base-install projection** captured
before a project bridge overlay exists. For a base-control variant, the raw
regular-file count and tree hash must match it exactly. For a bridge variant,
verification must:

1. enumerate and hash the exact allowed bridge, manifest, and generated-config
   paths as a separate overlay;
2. prove those paths do not replace a base file;
3. exclude only that allowlisted overlay and require the remaining regular-file
   count and tree hash to match the clean base capture; and
4. reject every unlisted added, removed, or changed file.

The raw whole-tree hash is expected to differ while an overlay is installed. It
must not overwrite or create a new meaning for the immutable base-build
manifest; the environment/fixture manifest binds the base identity and overlay
identity separately.
