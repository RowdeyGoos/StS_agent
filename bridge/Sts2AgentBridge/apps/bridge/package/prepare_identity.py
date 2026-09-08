"""Derive current package bindings from one candidate, without installing it."""
from pathlib import Path
import hashlib
import json
import sys
import release_package as package


def main():
    candidate = package.read_regular(Path(sys.argv[1]), 16 * 1024 * 1024)
    files = package.build_files(candidate)
    identity = {name: [len(data), hashlib.sha256(data).hexdigest()] for name, data in files.items()}
    if len(sys.argv) == 3:
        output = Path(sys.argv[2])
        if not output.is_absolute() or not output.is_relative_to('/private/tmp') or output.exists():
            raise ValueError('output_boundary')
        output.mkdir(mode=0o700)
        for name, data in files.items():
            with (output / name).open('xb') as stream:
                stream.write(data)
    print(json.dumps(identity, sort_keys=True))


if __name__ == '__main__':
    main()
