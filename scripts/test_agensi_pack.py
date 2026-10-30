"""Offline synthetic Git fixtures; never executes packaged content."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import agensi_audit_and_pack as pack


class PackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.blobs = {'SKILL.md': b'---\nname: fixture\ndescription: fixture\nmetadata:\n  version: 1.0.9\n---\n# Fixture\n',
                      'LICENSE': b'MIT fixture\n', 'README_EN.md': b'# Fixture\n',
                      'references/a.md': b'# Reference\n'}
        for name, data in self.blobs.items():
            file = self.repo / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')

    def test_deterministic_inventory_crc_sha_and_source_preservation(self):
        a, b = self.base / 'a.zip', self.base / 'b.zip'
        first = pack.check(self.repo, a)
        self.assertEqual(first['status'], 'PASS', first)
        self.assertEqual(pack.check(self.repo, b)['status'], 'PASS')
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(first['zip']['sha256'], hashlib.sha256(a.read_bytes()).hexdigest())
        with zipfile.ZipFile(a) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.namelist(), sorted(self.blobs))
            for name, data in self.blobs.items():
                self.assertEqual(z.read(name), data)
        self.assertEqual(self.git('status', '--porcelain'), b'')

    def test_excludes_repository_only_files(self):
        for name in ('agents/config.yaml', 'scripts/runtime.py', 'assets/image.png', 'README.md'):
            path = self.repo / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'not runtime knowledge')
        self.commit()
        result = pack.check(self.repo, self.base / 'whitelist.zip')
        self.assertEqual(result['status'], 'PASS', result)
        with zipfile.ZipFile(self.base / 'whitelist.zip') as z:
            self.assertEqual(z.namelist(), sorted(self.blobs))

    def test_bad_yaml_and_missing_reference_refused(self):
        for entry in (b'---\nname: [bad\ndescription: x\n---\nbody',
                      self.blobs['SKILL.md'] + b'`references/missing.md#anchor`'):
            self.assertTrue(pack.audit({**self.blobs, 'SKILL.md': entry})[0])

    def test_dirty_and_untracked_refused(self):
        for name in ('LICENSE', 'untracked'):
            path = self.repo / name
            old = path.read_bytes() if path.exists() else None
            path.write_text('modified')
            self.assertEqual(pack.check(self.repo)['status'], 'FAIL')
            if old is None:
                path.unlink()
            else:
                path.write_bytes(old)

    def test_symlink_source_and_ancestor_refused(self):
        (self.repo / 'references/link.md').symlink_to(self.base / 'secret')
        self.commit()
        self.assertEqual(pack.check(self.repo)['status'], 'FAIL')

    def test_hidden_worktree_change_refused(self):
        self.git('update-index', '--assume-unchanged', 'LICENSE')
        (self.repo / 'LICENSE').write_text('unreviewed')
        result = pack.check(self.repo, self.base / 'safe.zip')
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse((self.base / 'safe.zip').exists())

    def test_output_inside_existing_and_symlink_refused(self):
        self.assertEqual(pack.check(self.repo, self.repo / 'out.zip')['status'], 'FAIL')
        existing = self.base / 'existing.zip'
        existing.write_bytes(b'keep')
        self.assertEqual(pack.check(self.repo, existing)['status'], 'FAIL')
        self.assertEqual(existing.read_bytes(), b'keep')
        alias = self.base / 'alias'
        alias.symlink_to(self.base, target_is_directory=True)
        self.assertEqual(pack.check(self.repo, alias / 'new.zip')['status'], 'FAIL')

    def test_path_traversal_and_binary_nested_skill(self):
        for path in ('../escape', '/root', 'a\\b', 'a:b', 'a//b', 'a/./b', 'CON.txt', 'references/NUL', 'a.', 'a ', 'a\x7f'):
            self.assertFalse(pack.safe_name(path))
        for path, data in [('references/evil.exe', b'ascii'), ('references/SKILL.md', b'bad'), ('references/binary.md', b'\xff'), ('references/nul.md', b'\0')]:
            errors, _, _ = pack.audit({**self.blobs, path: data})
            self.assertTrue(errors, path)

    def test_case_collision_and_secret_pattern(self):
        self.assertTrue(pack.audit({**self.blobs, 'references/A.md': b'hi'})[0])
        data = b'-----BEGIN ' + b'PRIVATE KEY-----'
        errors, findings, _ = pack.audit({**self.blobs, 'references/secret.md': data})
        self.assertTrue(errors)
        self.assertEqual(findings[0]['rule'], 'private_key')

    def test_limits_and_failed_build_does_not_publish(self):
        with patch.object(pack, 'MAX_FILES', 3):
            self.assertTrue(pack.audit(self.blobs)[0])
        with patch.object(pack, 'MAX_CHARACTERS', 1):
            self.assertTrue(pack.audit(self.blobs)[0])
        target = self.base / 'oversize.zip'
        with patch.object(pack, 'MAX_BYTES', 1):
            self.assertEqual(pack.check(self.repo, target)['status'], 'FAIL')
        self.assertFalse(target.exists())
        self.assertEqual(list(self.base.glob('.agensi-*')), [])

    def test_crc_failure_does_not_publish(self):
        output = self.base / 'bad.zip'
        with patch.object(zipfile.ZipFile, 'testzip', return_value='SKILL.md'):
            self.assertEqual(pack.check(self.repo, output)['status'], 'FAIL')
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
