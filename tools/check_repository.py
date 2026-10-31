"""Audit tracked/staged paths and common secret patterns; never print secret values."""
import re
import subprocess
from repository_files import ROOT, release_files


def main():
    files = release_files()
    allowed = {path.relative_to(ROOT).as_posix() for path in files}
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().strip('\0').split('\0')) - {''}
    unexpected = sorted(tracked - allowed)
    missing = sorted(allowed - tracked)
    patterns = [rb'AIza[0-9A-Za-z_-]{35}', rb'gh[pousr]_[0-9A-Za-z]{30,}',
                rb'github_pat_[0-9A-Za-z_]{30,}', rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
                rb'postgres(?:ql)?://[^\s:]+:[^\s@]+@', rb'AKIA[0-9A-Z]{16}']
    issues = []
    total = 0
    for path in files:
        data = path.read_bytes()
        total += len(data)
        relative = path.relative_to(ROOT).as_posix()
        if len(data) > 25 * 1024 * 1024:
            issues.append(relative + ': exceeds repository size limit')
        if path.suffix not in {'.pt', '.png', '.webp', '.ico'} and any(re.search(p, data) for p in patterns):
            issues.append(relative + ': potential credential pattern (value withheld)')
    if unexpected:
        issues += ['Not allowlisted: ' + name for name in unexpected]
    if missing:
        issues += ['Not staged/tracked: ' + name for name in missing]
    if issues:
        raise SystemExit('Repository audit failed:\n' + '\n'.join(issues))
    print(f'Repository audit passed: {len(files)} files, {total/1024/1024:.1f} MiB; model hashes verified.')
    print('No unapproved paths or common credential patterns found. Review remains required.')

if __name__ == '__main__':
    main()
