import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

SPEC = importlib.util.spec_from_file_location('update_installer', Path(__file__).resolve().parents[1] / 'scripts/install_update.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True).stdout


@pytest.fixture
def update(tmp_path):
    repo = tmp_path / 'repo'; repo.mkdir()
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.name', 'Installer Test')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    (repo / 'app.txt').write_text('old\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'Baseline')
    (repo / 'app.txt').write_text('improved\n')
    patch = git(repo, 'diff', '--binary', 'HEAD')
    git(repo, 'restore', 'app.txt')
    package = tmp_path / 'package'; package.mkdir()
    (package / 'update.patch').write_bytes(patch)
    (package / 'update-manifest.json').write_text(json.dumps({
        'patch_sha256': hashlib.sha256(patch).hexdigest(),
        'files': [{'path': 'app.txt', 'before_sha256': hashlib.sha256(b'old\n').hexdigest()}],
    }))
    return repo, package


def test_installer_stages_new_branch_and_preserves_original(update):
    repo, package = update
    branch = installer.apply_update(repo, package)
    assert branch == 'pantone-improvements-v1.6.0'
    assert (repo / 'app.txt').read_text() == 'improved\n'
    assert git(repo, 'show', 'main:app.txt') == b'old\n'
    assert git(repo, 'diff', '--cached', '--name-only') == b'app.txt\n'
    assert git(repo, 'diff') == b''
    assert git(repo, 'rev-list', '--count', 'HEAD').strip() == b'1'


def test_installer_refuses_newer_committed_source_without_mutating(update):
    repo, package = update
    (repo / 'app.txt').write_text('newer user work\n')
    git(repo, 'commit', '-am', 'Newer work')
    with pytest.raises(RuntimeError, match='Your version differs'):
        installer.apply_update(repo, package)
    assert git(repo, 'branch', '--show-current').strip() == b'main'
    assert git(repo, 'status', '--porcelain') == b''
    assert (repo / 'app.txt').read_text() == 'newer user work\n'


def test_installer_refuses_uncommitted_work(update):
    repo, package = update
    (repo / 'notes.txt').write_text('user notes')
    with pytest.raises(RuntimeError, match='uncommitted or untracked'):
        installer.apply_update(repo, package)
    assert (repo / 'app.txt').read_text() == 'old\n'


def test_installer_refuses_damaged_package(update):
    repo, package = update
    (package / 'update.patch').write_text('damaged')
    with pytest.raises(RuntimeError, match='checksum'):
        installer.apply_update(repo, package)
    assert git(repo, 'status', '--porcelain') == b''
