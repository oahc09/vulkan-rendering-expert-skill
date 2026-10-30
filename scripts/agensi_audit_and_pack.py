#!/usr/bin/env python3
"""Offline repository preflight and deterministic Agensi website ZIP builder.

Python 3.9+, Git, PyYAML (release-only). No network or Agent/GPU validation.
Only committed, clean source is packaged. Output must be outside the checkout.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import zipfile
from host_contract import validate_documents

REQUIRED = {'SKILL.md', 'LICENSE', 'README_EN.md'}
MAX_CHARACTERS = 6_000_000
MAX_FILES = 201  # exactly one SKILL.md plus 200 other text files
MAX_BYTES = 50_000_000
BINARY_SUFFIXES = {'.exe', '.dll', '.so', '.dylib', '.bin', '.app', '.dmg', '.msi', '.deb', '.rpm', '.wasm', '.class', '.jar', '.war', '.png', '.jpg', '.pdf', '.zip'}
RULES = {
    'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'github_token': r'\b(?:gh[pousr]_[A-Za-z0-9_]{35,}|github_pat_[A-Za-z0-9_]{30,})\b',
    'google_key': r'\bAIza[0-9A-Za-z_\-]{35}\b',
    'aws_key': r'\b(?:AKIA|ASIA)[0-9A-Z]{16}\b',
    'remote_exec': r'\b(?:curl|wget)\b[^\n]{0,160}\|\s*(?:sudo\s+)?(?:ba)?sh\b',
    'destructive': r'\brm\s+-[a-z]*r[a-z]*f[a-z]*\b|\brm\s+-[a-z]*f[a-z]*r[a-z]*\b|Remove-Item[^\n]*-Recurse',
    'data_exfil': r'\b(?:curl|wget)\b[^\n]{0,150}(?:--data|--upload-file|--post-file)',
    'env_read': r'\b(?:process\.env|os\.environ)\b',
    'prompt_override': r'ignore (?:all )?(?:previous|system) instructions|绕过(?:系统|安全)(?:规则|约束)',
}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def safe_name(name):
    p = PurePosixPath(name)
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    return (bool(name) and not p.is_absolute()
            and all(x not in ('', '.', '..') and x == x.rstrip(' .')
                    and x.split('.')[0].upper() not in reserved for x in name.split('/'))
            and not any(c in name for c in '\\:<>\"|?*')
            and not any(ord(c) < 32 or ord(c) == 127 for c in name))


def snapshot(root):
    """Package immutable Git blobs; compare but never package working-file bytes."""
    top = Path(git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve()
    if root != top:
        raise ValueError('Expected checkout root')
    if git(root, 'status', '--porcelain=v1', '--untracked-files=all', '--ignore-submodules=none').strip():
        raise ValueError('Working tree is not clean (including untracked files)')
    revision = git(root, 'rev-parse', 'HEAD').decode().strip()
    records = git(root, 'ls-tree', '-rz', '--full-tree', revision).split(b'\0')
    blobs = {}
    count = 0
    for record in filter(None, records):
        meta, raw_name = record.split(b'\t', 1)
        mode, kind, oid = meta.decode('ascii').split()
        name = raw_name.decode('utf-8')
        count += 1
        if not safe_name(name):
            raise ValueError(f'Unsafe repository path: {name!r}')
        if mode not in ('100644', '100755') or kind != 'blob':
            raise ValueError(f'Symlink/submodule/non-regular source refused: {name}')
        # Reject working-tree symlinks even with skip-worktree/assume-unchanged.
        cursor = root
        for part in PurePosixPath(name).parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError(f'Symlink source refused: {name}')
        data = git(root, 'cat-file', 'blob', oid)
        if not cursor.is_file() or cursor.read_bytes() != data:
            raise ValueError(f'Working source differs from HEAD: {name}')
        if name in REQUIRED or name.startswith('references/'):
            blobs[name] = data
    return revision, count, dict(sorted(blobs.items()))


def audit(blobs):
    errors, findings = [], []
    missing = REQUIRED - blobs.keys()
    if missing:
        errors.append('Missing required files: ' + ', '.join(sorted(missing)))
    if len(blobs) > MAX_FILES:
        errors.append('200 additional text file limit exceeded')
    if sum(PurePosixPath(p).name == 'SKILL.md' for p in blobs) != 1:
        errors.append('Exactly one root SKILL.md required (no nested skills)')
    texts = {}
    if len({n.casefold() for n in blobs}) != len(blobs):
        errors.append('Case-insensitive path collision')
    for name, data in blobs.items():
        if not safe_name(name) or PurePosixPath(name).suffix.lower() in BINARY_SUFFIXES:
            errors.append(f'Unsafe/non-text package path: {name}')
        try:
            value = data.decode('utf-8')
        except UnicodeDecodeError:
            errors.append(f'Non-UTF8 file: {name}')
            continue
        if value.startswith('\ufeff') or '\x00' in value:
            errors.append(f'BOM or binary NUL: {name}')
        texts[name] = value
        for label, rule in RULES.items():
            for match in re.finditer(rule, value, re.I):
                findings.append({'file': name, 'line': value.count('\n', 0, match.start()) + 1, 'rule': label})
    chars = sum(len(text.encode('utf-16-le')) // 2 for text in texts.values())  # conservative UTF-16 units
    if chars > MAX_CHARACTERS:
        errors.append('6 million character limit exceeded')
    if findings:
        errors.append('Suspicious pattern matches require manual review')
    entry = texts.get('SKILL.md', '')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---\r?\n(.*)', entry, re.S)
    if not match or not match[2].strip():
        errors.append('Missing frontmatter or body')
    elif any(not re.search(rf'(?m)^{field}:\s*\S', match[1]) for field in ('name', 'description')):
        errors.append('Missing name/description')
    errors.extend(validate_documents(texts))
    return errors, findings, chars


def write_zip(blobs, output):
    """Build beside destination; validate before atomic publication, never overwrite."""
    if output.exists() or output.is_symlink():
        raise ValueError('Output already exists; refusing overwrite')
    if not output.parent.is_dir():
        raise ValueError('Output parent must already exist')
    fd, temporary = tempfile.mkstemp(prefix='.agensi-', suffix='.zip', dir=output.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, data in sorted(blobs.items()):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                z.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        if Path(temporary).stat().st_size > MAX_BYTES:
            raise ValueError('50 MB website ZIP size limit exceeded')
        with zipfile.ZipFile(temporary) as z:
            if z.testzip() is not None or z.namelist() != sorted(blobs):
                raise ValueError('ZIP CRC/inventory validation failed')
            for name, data in blobs.items():
                if hashlib.sha256(z.read(name)).digest() != hashlib.sha256(data).digest():
                    raise ValueError(f'ZIP content SHA mismatch: {name}')
        digest = hashlib.sha256(Path(temporary).read_bytes()).hexdigest()
        os.link(temporary, output)  # exclusive destination creation, unlike replace()
        return {'path': str(output), 'size_bytes': output.stat().st_size, 'sha256': digest, 'crc_verified': True}
    finally:
        Path(temporary).unlink(missing_ok=True)


def check(root, output=None):
    root = Path(root).resolve()
    report = {'status': 'FAIL', 'errors': [], 'zip': None,
              'scope': 'Offline committed-text pattern/structure scan; not a security guarantee, platform approval, remote accuracy or Agent/GPU validation'}
    try:
        if output:
            output = Path(output).absolute()
            if any(p.is_symlink() for p in (output, *output.parents)):
                raise ValueError('Symlink output path refused')
            resolved = output.resolve()
            if resolved == root or root in resolved.parents:
                raise ValueError('Output must be outside checkout')
            output = resolved
        revision, count, blobs = snapshot(root)
        errors, findings, chars = audit(blobs)
        report.update(revision=revision, tracked_files=count, package_files=len(blobs), package_characters=chars,
                      errors=errors, findings=findings,
                      files=[{'path': n, 'sha256': hashlib.sha256(d).hexdigest()} for n, d in blobs.items()])
        if not errors and output:
            # Recheck cleanliness/HEAD before publishing the immutable snapshot.
            if snapshot(root)[0] != revision:
                raise ValueError('HEAD changed during audit')
            report['zip'] = write_zip(blobs, output)
        report['status'] = 'FAIL' if errors else 'PASS'
    except (ValueError, OSError, UnicodeError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
        report['errors'].append(str(exc))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = check(args.repo, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
