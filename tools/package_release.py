"""Build a release with the same explicit allowlist used for GitHub review."""
import hashlib
import json
import zipfile
from repository_files import ROOT, release_files


def main():
    files = release_files()
    target = ROOT/'dist/PetVision-deployment.zip'
    target.parent.mkdir(exist_ok=True)
    hashes = {}
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            archive.writestr(relative, data)
            hashes[relative] = hashlib.sha256(data).hexdigest()
        archive.writestr('RELEASE-MANIFEST.json', json.dumps(hashes, indent=2))
    print(f'{target.name}: {len(hashes)} files, {target.stat().st_size/1024/1024:.1f} MiB')

if __name__ == '__main__':
    main()
