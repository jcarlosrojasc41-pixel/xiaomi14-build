#!/usr/bin/env python3
"""Check the public file allowlist, checksums and common accidental secrets."""
import hashlib
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TOP = {'.gitignore', 'README.md', 'NOTICE.md', 'default.xml', 'PUBLIC_FILES.sha256'}
FILES = {
    'docs': {'BUILD-zh.md', 'SOURCES-zh.md', 'VALIDATION-zh.md'},
    'environment': {'Containerfile', 'check-host.py', 'packages-reference.tsv'},
    'scripts': {'reproduce.py', 'check-public.py', 'publish-github.sh'},
    'locks': {'baseline.json', 'build.json', 'downloads.json', 'kernel.json', 'lfs.json',
              'patched-files.json', 'patches.json', 'vendor-inputs.json', 'vendor-outputs.json'},
    'patches': {'houji-pixelos-product.patch', 'houji-cn-esim-omission.patch',
                'sm8650-common-cn-esim-omission.patch', 'sm8650-common-extraction-fixup-paths.patch',
                'vendor-custom-reproducible-date.patch', 'vendor-lineage-reproducible-date.patch',
                'build-make-ramdisk-property-reader.patch'},
}
ALLOWED = TOP | {folder + '/' + name for folder, names in FILES.items() for name in names}


def main():
    tracked = set(subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode().strip('\0').split('\0'))
    if tracked != ALLOWED:
        raise SystemExit('Public file allowlist mismatch: ' + str(tracked ^ ALLOWED))
    hashes = {}
    for line in (ROOT / 'PUBLIC_FILES.sha256').read_text().splitlines():
        sha, name = line.split('  ', 1)
        if name in hashes or name not in ALLOWED:
            raise SystemExit('Invalid checksum inventory')
        hashes[name] = sha
    if set(hashes) != ALLOWED - {'PUBLIC_FILES.sha256'}:
        raise SystemExit('Incomplete checksum inventory')
    for name in sorted(ALLOWED):
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
            raise SystemExit('Unexpected file type or size: ' + name)
        data = path.read_bytes()
        text = data.decode('utf-8')
        if name in hashes and hashlib.sha256(data).hexdigest() != hashes[name]:
            raise SystemExit('Checksum mismatch: ' + name)
        secret = r'(?:gh[opsu]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)'
        if re.search(secret, text):
            raise SystemExit('Possible credential in ' + name)
        if name != 'scripts/check-public.py' and re.search(r'/(?:home|Users)/|"(?:imei|imsi|iccid|serial_number)"\s*:', text, re.I):
            raise SystemExit('Local path or device identifier field in ' + name)
    print(f'Public allowlist and checksums passed: {len(ALLOWED)} text files; no image/APK/archive/backups.')


if __name__ == '__main__':
    main()
