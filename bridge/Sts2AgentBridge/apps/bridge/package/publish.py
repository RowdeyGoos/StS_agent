"""Publish the accepted package to the fixed disposable install-input directory."""
import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-manifest', type=Path, required=True)
    parser.add_argument('--release-sha256', required=True)
    parser.add_argument('--dll', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).absolute().parents[3]
    sys.path.insert(0, str(root))
    from release_support import verify_release_sources
    verify_release_sources(root, 'bridge', args.release_manifest, args.release_sha256)
    import release_package as package
    files = package.canonical_files(package.read_regular(args.dll, 16 * 1024 * 1024))
    package.publish_verified(files)
    print(package.ARTIFACT_ROOT)


if __name__ == '__main__':
    main()
