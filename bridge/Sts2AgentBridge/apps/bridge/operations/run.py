#!/usr/bin/env python3
"""Verify one accepted release before installing or cleaning up its owned files."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-manifest', type=Path, required=True)
    parser.add_argument('--release-sha256', required=True)
    parser.add_argument('--mode', choices=['install', 'quarantine', 'purge'], required=True)
    parser.add_argument('--expected-state-sha256')
    args = parser.parse_args()
    root = Path(__file__).absolute().parents[3]
    sys.path.insert(0, str(root))
    from release_support import verify_release_sources
    verify_release_sources(root, 'bridge', args.release_manifest, args.release_sha256)
    import manage_live_campaign as manager
    # These are account-root facts; no game profile/save is opened here.
    import pwd
    account = pwd.getpwuid(os.geteuid())
    command = ['--mode', args.mode, '--user-profile', account.pw_dir, '--effective-uid', str(account.pw_uid)]
    if args.mode == 'install':
        command += ['--artifact-root', str(manager.ARTIFACT_ROOT), '--flow-kind', 'unified']
    else:
        if not args.expected_state_sha256:
            parser.error('--expected-state-sha256 is required for owned cleanup')
        command += ['--expected-state-sha256', args.expected_state_sha256]
    sys.argv = [str(Path(__file__)), *command]
    manager.main(manager.operation)


if __name__ == '__main__':
    main()
