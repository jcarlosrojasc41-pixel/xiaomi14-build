#!/usr/bin/env python3
"""Portable, hash-locked houji build recipe. Never accesses a phone."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILTERS = ['-c', 'filter.lfs.clean=git-lfs clean -- %f',
           '-c', 'filter.lfs.smudge=git-lfs smudge -- %f',
           '-c', 'filter.lfs.process=git-lfs filter-process',
           '-c', 'filter.lfs.required=true']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(name):
    return json.loads((ROOT / 'locks' / (name + '.json')).read_text())


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args, cwd=None, capture=False, env=None):
    return subprocess.run([str(x) for x in args], cwd=cwd, check=True,
                          stdout=subprocess.PIPE if capture else None,
                          text=True, env=env).stdout


def git(path, *args):
    return run(['git', '--no-optional-locks', *FILTERS, '-C', path, *args], capture=True).strip()


def safe(root, relative):
    require(relative and not relative.startswith('/') and
            all(p not in ('', '.', '..') for p in relative.split('/')), 'Unsafe path: ' + relative)
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()), 'Path leaves root: ' + str(path))
    return path


def check_file(path, row):
    require(path.is_file() and not path.is_symlink(), 'Missing regular file: ' + str(path))
    require(path.stat().st_size == row['bytes'], 'Size mismatch: ' + str(path))
    if 'sha256' in row:
        require(digest(path) == row['sha256'], 'SHA-256 mismatch: ' + str(path))
    if 'git_blob_sha1' in row:
        data = path.read_bytes()
        require(hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                == row['git_blob_sha1'], 'Git blob mismatch: ' + str(path))


def source_revisions():
    return {p.get('path', p.get('name')): p.get('revision')
            for p in ET.parse(ROOT / 'default.xml').getroot().findall('project')}


class Recipe:
    def __init__(self, args):
        self.args = args
        self.work = args.work.resolve()
        self.source = (args.source or self.work / 'source').resolve()
        require(not self.work.is_relative_to(ROOT), 'Keep downloads/source/output outside this public repository')

    def container(self, command):
        self.work.mkdir(parents=True, exist_ok=True)
        return run(['podman', 'run', '--rm', '--network=none', '--http-proxy=false',
                    '--userns=keep-id:uid=1001,gid=1001', '--hostname=xiaomi14-build',
                    '-v', str(self.source) + ':/work:z',
                    '-v', str(self.work) + ':/inputs:z',
                    *sum((['--env', k + '=' + v] for k, v in load('build')['environment'].items()), []),
                    self.args.image, *command])

    def init(self):
        self.source.mkdir(parents=True, exist_ok=True)
        require(not any(self.source.iterdir()), 'init requires an empty source directory')
        baseline = load('baseline')
        run(['repo', 'init', '-u', str(ROOT), '-b', git(ROOT, 'rev-parse', 'HEAD'),
             '-m', 'default.xml', '--repo-url', baseline['repo_tool_url'],
             '--repo-rev', baseline['repo_tool_commit'], '--git-lfs', '--no-clone-bundle'], cwd=self.source)

    def sync(self):
        env = {**os.environ, 'GIT_LFS_SKIP_SMUDGE': '1'}
        run(['repo', 'sync', '-c', '--no-clone-bundle', '-j', str(self.args.jobs)], cwd=self.source, env=env)
        print('Source sync finished. Run download, then lfs before configure/verify.')

    def download(self):
        target = self.work / 'downloads'
        target.mkdir(parents=True, exist_ok=True)
        for row in load('downloads'):
            if not row['required'] and not self.args.include_reference_kernel:
                continue
            path = target / row['filename']
            if path.exists():
                check_file(path, row)
                print('Verified cached', row['id'], flush=True)
                continue
            print('Downloading', row['id'], flush=True)
            partial = path.with_suffix(path.suffix + '.partial')
            with urllib.request.urlopen(row['url'], timeout=120) as src, partial.open('wb') as dst:
                shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
            check_file(partial, row)
            partial.replace(path)

    def lfs(self):
        rust = self.source / 'external/rust/android-crates-io'
        row = next(x for x in load('downloads') if x['id'] == 'rust-lfs-fixture')
        fixture = self.work / 'downloads' / row['filename']
        check_file(fixture, row)
        record = load('lfs')[0]
        require(git(rust, 'rev-parse', 'HEAD') == record['revision'], 'Rust source revision mismatch')
        rel = record['files'][0]['path']
        pointer = ('version https://git-lfs.github.com/spec/v1\noid sha256:' + row['sha256']
                   + '\nsize ' + str(row['bytes']) + '\n')
        require(git(rust, 'show', 'HEAD:' + rel) == pointer.strip(), 'Unexpected original LFS pointer')
        indexed = run(['git', '-C', rust, 'show', ':' + rel], capture=True)
        require(indexed == pointer, 'Rust fixture index has local changes')
        destination = rust / rel
        require(destination.read_bytes() in (pointer.encode(), fixture.read_bytes()), 'Fixture has local changes')
        gitdir = Path(git(rust, 'rev-parse', '--absolute-git-dir'))
        attrs = gitdir / 'info/attributes'
        rule = rel + ' filter=lfs diff=lfs merge=lfs -text\n'
        old = attrs.read_text() if attrs.exists() else ''
        require(not old or old.endswith('\n'), 'Malformed local attributes')
        if rule not in old.splitlines(keepends=True):
            attrs.parent.mkdir(parents=True, exist_ok=True)
            attrs.write_text(old + rule)
        oid = row['sha256']
        cache = gitdir / 'lfs/objects' / oid[:2] / oid[2:4] / oid
        cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture, cache)
        shutil.copyfile(fixture, destination)
        for project in load('lfs')[1:]:
            path = self.source / project['project']
            require(git(path, 'rev-parse', 'HEAD') == project['revision'], 'GMS revision mismatch')
            run(['git', *FILTERS, '-C', path, 'lfs', 'pull'])
        self.verify_lfs()

    def verify_lfs(self):
        for project in load('lfs'):
            for row in project['files']:
                check_file(self.source / project['project'] / row['path'],
                           {'bytes': row['size'], 'sha256': row['sha256']})

    def check_patched(self, project, record):
        base = self.source / project
        actual = git(base, '-c', 'status.renames=false', 'status', '--porcelain=v1', '--untracked-files=all')
        expected = '\n'.join(x['status'] + ' ' + x['path'] for x in record['dirty_paths']).strip()
        require(actual == expected, 'Unrecorded changes in ' + project)
        for row in record['files']:
            path = safe(base, row['path'])
            if row['state'] == 'deleted':
                require(not path.exists() and not path.is_symlink(), 'Unexpected deleted-file replacement')
            else:
                check_file(path, row)
                require(path.stat().st_mode & 0o777 == int(row['expected_git_mode'], 8) & 0o777,
                        'Patched file mode differs: ' + str(path))

    def check_kernel(self, allow_original=False):
        lock = load('kernel')
        base = self.source / 'device/xiaomi/houji-kernel'
        require(git(base, 'rev-parse', 'HEAD') == lock['revision'], 'Kernel revision mismatch')
        tracked = set(git(base, 'ls-files').splitlines())
        require(tracked == {x['path'] for x in lock['files'] + lock['headers'] + lock['omitted']},
                'Kernel tracked inventory mismatch')
        for row in lock['files'] + lock['headers']:
            path = safe(base, row['path'])
            check_file(path, row)
            require(path.stat().st_mode & 0o777 == int(row['mode'], 8) & 0o777, 'Kernel file mode mismatch')
        for row in lock['omitted']:
            path = safe(base, row['path'])
            if allow_original and path.exists():
                check_file(path, {'bytes': row['expected_bytes'], 'git_blob_sha1': row['expected_git_blob_sha1']})
            else:
                require(not path.exists() and not path.is_symlink(), 'Stale kernel module remains: ' + str(path))
        actual = git(base, '-c', 'status.renames=false', 'status', '--porcelain=v1', '--untracked-files=all')
        expected = '\n'.join(' D ' + x['path'] for x in sorted(lock['omitted'], key=lambda x: x['path'])
                             if not (base / x['path']).exists()).strip()
        require(actual == expected, 'Unrecorded kernel changes')

    def configure(self):
        records = load('patched-files')
        patches = load('patches')
        for row in patches:
            require(digest(ROOT / row['file']) == row['sha256'], 'Patch hash mismatch')
        for project, record in records.items():
            path = self.source / project
            require(git(path, 'rev-parse', 'HEAD') == record['revision'], 'Patch base revision mismatch')
            if git(path, 'status', '--porcelain=v1', '--untracked-files=all'):
                self.check_patched(project, record)
                continue
            # Preflight the entire patch sequence against exact original touched files.
            with tempfile.TemporaryDirectory(prefix='houji-patch-check-') as tmp:
                test = Path(tmp)
                run(['git', 'init', '-q', test])
                for row in record['files']:
                    if row['base_blob'] is not None:
                        dest = test / row['path']
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        data = subprocess.check_output(['git', '-C', str(path), 'cat-file', 'blob', row['base_blob']])
                        dest.write_bytes(data)
                        mode = git(path, 'ls-tree', 'HEAD', '--', row['path']).split()[0]
                        dest.chmod(int(mode, 8) & 0o777)
                selected = [x for x in patches if x['project_path'] == project]
                for patch in selected:
                    run(['git', '-C', test, 'apply', '--check', ROOT / patch['file']])
                    run(['git', '-C', test, 'apply', ROOT / patch['file']])
                for row in record['files']:
                    if row['state'] != 'deleted':
                        check_file(test / row['path'], row)
                for patch in selected:
                    run(['git', '-C', path, 'apply', ROOT / patch['file']])
            self.check_patched(project, record)
        self.check_kernel(allow_original=True)
        for row in load('kernel')['omitted']:
            (self.source / 'device/xiaomi/houji-kernel' / row['path']).unlink(missing_ok=True)
        self.check_kernel()
        print('Seven patches and curated kernel verified.')

    def extract(self):
        lock = load('vendor-inputs')
        for archive in load('downloads'):
            name = archive['id']
            if name not in ('china-os2', 'global-os3'):
                continue
            zip_path = self.work / 'downloads' / archive['filename']
            check_file(zip_path, archive)
            base = self.work / 'dumps' / name
            require(not base.exists(), 'Extraction output already exists: ' + str(base))
            images = base / 'images'
            images.mkdir(parents=True)
            with zipfile.ZipFile(zip_path) as z, z.open('payload.bin') as src, (base / 'payload.bin').open('wb') as dst:
                shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
            img_records = [x for x in lock['images'] if x['source_set'] == name]
            for row in img_records:
                self.container(['/work/prebuilts/extract-tools/linux-x86/bin/ota_extractor',
                                '--payload', '/inputs/dumps/' + name + '/payload.bin',
                                '--output-dir', '/inputs/dumps/' + name + '/images', '--partitions', row['partition']])
                check_file(images / (row['partition'] + '.img'), row)
            partitions = sorted({x['source'].split('/')[1] for x in lock['files']
                                 if x['source_set'] == name and x['source'].startswith('files/')})
            for partition in partitions:
                image = images / (partition + '.img')
                dest = base / 'files' / partition
                dest.mkdir(parents=True)
                with image.open('rb') as stream:
                    stream.seek(1024)
                    magic = stream.read(4)
                src = '/inputs/dumps/' + name + '/images/' + image.name
                out = '/inputs/dumps/' + name + '/files/' + partition
                if magic == bytes.fromhex('e2e1f5e0'):
                    self.container(['fsck.erofs', '--extract=' + out, src])
                else:
                    require(' ' not in out, 'debugfs extraction requires a work path without spaces')
                    self.container(['debugfs', '-R', 'rdump / ' + out, src])
            (base / 'payload.bin').unlink()
        print('Pinned Xiaomi images extracted; next run stage.')

    def stage(self):
        output = self.work / 'vendor-inputs'
        require(not output.exists(), 'Refusing to replace existing vendor staging')
        lock = load('vendor-inputs')
        for row in lock['files']:
            check_file(safe(self.work / 'dumps' / row['source_set'], row['source']), row)
        with tempfile.TemporaryDirectory(prefix='.vendor-', dir=self.work) as tmp:
            stage = Path(tmp) / 'staged'
            stage.mkdir()
            for row in lock['files']:
                src = safe(self.work / 'dumps' / row['source_set'], row['source'])
                dst = safe(stage / row['module'], row['destination'])
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                dst.chmod(int(row['mode'], 8))
                check_file(dst, row)
            stage.rename(output)
        print('Verified 3,195 primary blobs, 21 firmware images and one lookup alias.')

    def generate(self):
        lock = load('vendor-inputs')
        for row in lock['files']:
            check_file(self.work / 'vendor-inputs' / row['module'] / row['destination'], row)
        for name, sha in lock['source_lists'].items():
            require(digest(self.source / 'device/xiaomi' / name / 'proprietary-files.txt') == sha,
                    'Proprietary source list mismatch')
        for module in ('houji', 'sm8650-common'):
            require(not (self.source / 'vendor/xiaomi' / module).exists(), 'Vendor output already exists; use verify')
        for flag, name in [('--only-common', 'sm8650-common'), ('--only-target', 'houji')]:
            self.container(['env', 'PYTHONPATH=/work/tools/extract-utils', 'python3',
                            'device/xiaomi/houji/extract-files.py', flag, '/inputs/vendor-inputs/' + name])
        self.verify_vendor()

    def verify_vendor(self):
        rows = load('vendor-outputs')
        found = set()
        for name in ('houji', 'sm8650-common'):
            for path in (self.source / 'vendor/xiaomi' / name).rglob('*'):
                if path.is_file() or path.is_symlink():
                    found.add(path.relative_to(self.source).as_posix())
        require(found == {x['path'] for x in rows}, 'Generated vendor file inventory differs')
        for row in rows:
            path = self.source / row['path']
            if 'link' in row:
                require(path.is_symlink() and os.readlink(path) == row['link'], 'Vendor symlink mismatch')
            else:
                check_file(path, row)
                require(path.stat().st_mode & 0o777 == int(row['mode'], 8), 'Vendor output mode mismatch')

    def verify(self):
        revisions = source_revisions()
        require(len(revisions) == 1236, 'Unexpected project count')
        patched = load('patched-files')
        allowed = set(patched) | {'device/xiaomi/houji-kernel'}
        def check(item):
            name, rev = item
            path = self.source / name
            require(git(path, 'rev-parse', 'HEAD') == rev, 'HEAD mismatch: ' + name)
            if name not in allowed:
                require(not git(path, 'status', '--porcelain=v1', '--untracked-files=all'), 'Unrecorded changes: ' + name)
        with ThreadPoolExecutor(max_workers=self.args.jobs) as pool:
            list(pool.map(check, revisions.items()))
        for project, record in patched.items():
            self.check_patched(project, record)
        self.check_kernel()
        self.verify_lfs()
        self.verify_vendor()
        print('Verified 1,236 HEADs, recorded local changes, kernel/headers, nine LFS files and generated vendor bytes.')

    def build(self):
        self.verify()
        self.container(['bash', '-e', '-c', 'source build/envsetup.sh && breakfast houji userdebug && m pixelos -j' + str(self.args.jobs)])
        self.verify()
        print('Build and input revalidation finished. Review/signature-check the new OTA before installation.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True, help='Private build workspace outside this repository')
    parser.add_argument('--source', type=Path, help='Override WORK/source (useful for read-only verification)')
    parser.add_argument('--image', default='localhost/pixelos-build:ubuntu24.04')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--include-reference-kernel', action='store_true')
    parser.add_argument('command', choices=['init', 'sync', 'download', 'lfs', 'configure', 'extract', 'stage', 'generate', 'verify', 'build'])
    args = parser.parse_args()
    require(1 <= args.jobs <= 64, 'jobs must be between 1 and 64')
    getattr(Recipe(args), args.command)()


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit('Stopped: ' + str(error))
