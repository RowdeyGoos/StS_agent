from __future__ import annotations
import sys
import os
import shutil
import tempfile
from unittest import mock
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).parent))
import release_package as package

class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = package.canonical_files(package.read_regular(Path(sys.argv[1]), 95232))

    def test_reproduction(self):
        self.assertEqual(self.files, package.canonical_files(self.files[package.DLL_NAME]))
        package.verify_files(self.files)

    def test_each_artifact_byte(self):
        for name in self.files:
            with self.subTest(name=name):
                changed = dict(self.files)
                changed[name] = b'X' + changed[name][1:]
                with self.assertRaises(ValueError):
                    package.verify_files(changed)

    def test_inventory_and_framing(self):
        for operation in ('extra', 'missing', 'old_name', 'zip_trailing', 'manifest_lf', 'zip_truncated'):
            with self.subTest(operation=operation):
                changed = dict(self.files)
                if operation == 'extra': changed['extra.pdb'] = b''
                elif operation == 'missing': del changed[package.MANIFEST_NAME]
                elif operation == 'old_name': changed['Sts2AgentBridge.dll'] = changed.pop(package.DLL_NAME)
                elif operation == 'zip_trailing': changed[package.ZIP_NAME] += b'X'
                elif operation == 'manifest_lf': changed[package.MANIFEST_NAME] = changed[package.MANIFEST_NAME][:-1]
                else: changed[package.ZIP_NAME] = changed[package.ZIP_NAME][:-1]
                with self.assertRaises(ValueError): package.verify_files(changed)

    def test_publisher_success_and_no_adoption(self):
        for preexisting in (False, True):
            root = Path(tempfile.mkdtemp(prefix='item-package-publish-', dir='/private/tmp'))
            if not preexisting: root.rmdir()
            try:
                with mock.patch.object(package, 'ARTIFACT_ROOT', root):
                    if preexisting:
                        sentinel=root/'sentinel'; sentinel.write_bytes(b'untouched')
                        with self.assertRaises(FileExistsError): package.publish_verified(self.files)
                        self.assertEqual(sentinel.read_bytes(),b'untouched')
                        self.assertEqual({p.name for p in root.iterdir()},{'sentinel'})
                    else:
                        package.publish_verified(self.files)
                        self.assertEqual({p.name for p in root.iterdir()},set(self.files))
                        for name,data in self.files.items():
                            self.assertEqual(package.read_regular(root/name,len(data)),data)
                        with self.assertRaises(FileExistsError): package.publish_verified(self.files)
            finally: shutil.rmtree(root)

    def test_reader_rejects_unsafe_and_changed_inputs(self):
        for mutation in ('link','hardlink','oversize','directory','changed'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(prefix='item-package-input-',dir='/private/tmp') as directory:
                root=Path(directory); path=root/'input'; path.write_bytes(b'abcd')
                if mutation=='link': path.rename(root/'target'); path.symlink_to('target')
                elif mutation=='hardlink': os.link(path,root/'alias')
                elif mutation=='directory': path.unlink(); path.mkdir()
                original=package.os.read
                fired=False
                def changing(fd, size):
                    nonlocal fired
                    data=original(fd,size)
                    if mutation=='changed' and data and not fired:
                        fired=True; path.write_bytes(b'efgh')
                    return data
                with mock.patch.object(package.os,'read',changing):
                    with self.assertRaises(ValueError): package.read_regular(path,3 if mutation=='oversize' else 4)
                if mutation=='changed': self.assertTrue(fired)

if __name__ == '__main__':
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(PackageTests))
    if result.wasSuccessful(): print('{"schema_version":1,"status":"passed","suite":"item_v1_package","check_count":5,"mutation_cases":9}')
    raise SystemExit(0 if result.wasSuccessful() else 1)
