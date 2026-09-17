#!/usr/bin/env python3
"""Apply the reviewed v1.6 update on a new local Git branch. No push or merge."""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path


def git(repo, *args, check=True):
    completed = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if check and completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or 'Git command failed.')
    return completed


def apply_update(repo: Path, package: Path) -> str:
    repo = repo.expanduser().resolve()
    package = package.resolve()
    patch = package / 'update.patch'
    manifest = json.loads((package / 'update-manifest.json').read_text())
    if hashlib.sha256(patch.read_bytes()).hexdigest() != manifest['patch_sha256']:
        raise RuntimeError('The update package checksum does not match. Download it again.')
    if Path(git(repo, 'rev-parse', '--show-toplevel').stdout.strip()).resolve() != repo:
        raise RuntimeError('Select the repository root: the folder containing pyproject.toml.')
    if git(repo, 'status', '--porcelain', '--untracked-files=all').stdout.strip():
        raise RuntimeError('Your repository has uncommitted or untracked work. Commit or move that work first; no files were changed.')
    conflicts = []
    for item in manifest['files']:
        relative = Path(item['path'])
        target = repo / relative
        if relative.is_absolute() or '..' in relative.parts or not target.resolve().is_relative_to(repo):
            raise RuntimeError('The package contains an invalid destination path.')
        expected = item['before_sha256']
        if expected is None:
            if target.exists() or target.is_symlink():
                conflicts.append(item['path'])
        elif not target.is_file() or target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            conflicts.append(item['path'])
    if conflicts:
        base_label = manifest.get('base_description', 'reviewed source files')
        raise RuntimeError(f'Your version differs from {base_label}. No files were changed. Share a fresh repository ZIP to adapt this update. Different files:\n' + '\n'.join(conflicts))
    git(repo, 'apply', '--check', str(patch))
    branch = 'pantone-improvements-v1.6.0'
    suffix = 2
    while git(repo, 'show-ref', '--verify', '--quiet', 'refs/heads/' + branch, check=False).returncode == 0:
        branch = f'pantone-improvements-v1.6.0-{suffix}'
        suffix += 1
    original_branch = git(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False).stdout.strip()
    original_head = git(repo, 'rev-parse', 'HEAD').stdout.strip()
    git(repo, 'switch', '-c', branch)
    applied = git(repo, 'apply', '--index', str(patch), check=False)
    if applied.returncode:
        # git apply is atomic unless --reject is requested (this installer never uses it).
        git(repo, 'switch', original_branch or original_head)
        raise RuntimeError('Git could not apply the update. Original branch restored; empty update branch retained.\n' + applied.stderr)
    return branch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True, help='Local Pantone Challenger Git repository folder')
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        branch = apply_update(args.repo, args.package)
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        print('UPDATE STOPPED: ' + str(exc), file=sys.stderr)
        return 1
    print('\nUpdate applied on branch: ' + branch)
    print('Your original branch is preserved. Nothing was pushed, merged, or published.')
    print('Review and commit the changes in GitHub Desktop, then Publish branch and Create Pull Request.')
    print('Terminal alternative:\n  cd ' + shlex.quote(str(args.repo.expanduser().resolve())))
    print('  git diff --cached --stat')
    print('  git commit -m "Improve Pantone Challenger measurement and optional AI review"')
    print('  git push -u origin ' + shlex.quote(branch))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
