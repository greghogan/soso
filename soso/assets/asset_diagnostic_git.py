"""Publish only the reviewed diagnostic, without moving the local branch or index."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

WORKFLOW = '.github/workflows/inspect-asset-identity.yml'
MAIN = 'refs/heads/main'


def git(root, *args, data=None, index=None):
    env = dict(os.environ)
    for key in ('GIT_DIR', 'GIT_COMMON_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE',
                'GIT_NAMESPACE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'):
        env.pop(key, None)
    if index is not None:
        env['GIT_INDEX_FILE'] = str(index)
    result = subprocess.run(['git', '-C', str(root), '-c', 'remote.origin.mirror=false', *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if result.returncode:
        raise ValueError(f'Git {args[0]} failed. No force push was attempted. Check Git access and whether remote main changed, then rerun.')
    return result.stdout


def github_origin(root, repo):
    for flags in ((), ('--push',)):
        urls = git(root, 'remote', 'get-url', *flags, '--all', 'origin').decode().splitlines()
        if len(urls) != 1 or not re.fullmatch(
                r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)' +
                re.escape(repo) + r'(?:\.git)?/?', urls[0], re.IGNORECASE):
            raise ValueError(f'Git origin must have one fetch URL and one push URL for github.com/{repo}. Nothing was published.')


def remote_main(root):
    response = git(root, 'ls-remote', '--symref', '--exit-code', 'origin', 'HEAD', MAIN).decode().splitlines()
    if f'ref: {MAIN}\tHEAD' not in response:
        raise ValueError('GitHub workflow dispatch requires the remote default branch to be main. Nothing was published.')
    tips = [line.split()[0] for line in response if re.fullmatch(r'[a-f0-9]{40,64}\t' + MAIN, line)]
    if len(tips) != 1:
        raise ValueError('Could not establish remote main. Nothing was published.')
    return tips[0]


def publish(root, repo, path, ask):
    github_origin(root, repo)
    base = remote_main(root)
    git(root, 'fetch', '--no-tags', '--no-write-fetch-head', '--no-recurse-submodules', 'origin', base)
    content = path.read_bytes()
    entry = git(root, 'ls-tree', base, '--', WORKFLOW)
    if entry:
        if entry.startswith(b'100644 blob ') and git(root, 'show', f'{base}:{WORKFLOW}') == content:
            print(f'The identical diagnostic is already published on {repo} main.')
            if ask(f'Run the diagnostic on {repo} main? [y/N]: ').strip().lower() not in ('y', 'yes'):
                return None
            return base
        raise ValueError('Remote main already has a different diagnostic. It was not overwritten.')
    with tempfile.TemporaryDirectory(prefix='soso-diagnostic-') as directory:
        index = Path(directory) / 'index'
        git(root, 'read-tree', base, index=index)
        blob = git(root, 'hash-object', '-w', '--stdin', data=content).decode().strip()
        git(root, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{WORKFLOW}', index=index)
        tree = git(root, 'write-tree', index=index).decode().strip()
    if git(root, 'diff-tree', '--name-only', '-r', '-z', base, tree) != WORKFLOW.encode() + b'\0':
        raise ValueError('Proposed commit is not limited to the diagnostic. Nothing was published.')
    commit = git(root, 'commit-tree', tree, '-p', base, '-m',
                 'Add GitHub workflow identity diagnostic').decode().strip()
    print(f'The script will publish only the diagnostic to {repo} main and run it. Publishing may trigger Pages.')
    if ask('Publish and run the GitHub identity diagnostic? [y/N]: ').strip().lower() not in ('y', 'yes'):
        print('Nothing published or run. Rerun setup when ready.')
        return None
    github_origin(root, repo)
    if remote_main(root) != base:
        raise ValueError('Remote main changed while awaiting approval. Nothing was published; rerun setup.')
    git(root, 'push', '--no-follow-tags', '--recurse-submodules=no', 'origin', f'{commit}:{MAIN}')
    if remote_main(root) != commit:
        raise ValueError('Push returned success, but remote main has since changed. Check GitHub before continuing.')
    print(f'Published diagnostic commit {commit[:12]} to {repo} main.')
    return commit
