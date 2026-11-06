"""Verify published dataset identity and retained files without extracting images."""
from pathlib import Path
import collections
import hashlib
import json
import zipfile

HERE = Path(__file__).resolve().parent

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    checks = json.loads((HERE / 'checksums.json').read_text())
    for name, expected in checks.items():
        p = HERE / name
        assert p.stat().st_size == expected['bytes'], f'Size mismatch: {name}'
        assert digest(p) == expected['sha256'], f'Archive hash mismatch: {name}'
        print('Archive verified:', name)
    manifest = json.loads((HERE / 'training_manifest.json').read_text())
    identity = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    assert checks['PetVision_dataset_v2.zip']['sha256'] == manifest['archive_sha256']
    for species in ('cat', 'dog'):
        metadata = json.loads((HERE.parent / 'ml/artifacts/curated-v2' / species / 'model_metadata.json').read_text())
        assert identity == metadata['manifest_hash'], f'Model manifest mismatch: {species}'
    records = manifest['included']
    assert len(records) == 1108
    groups, hashes = collections.defaultdict(set), collections.defaultdict(set)
    paths = set()
    with zipfile.ZipFile(HERE / 'PetVision_dataset_v2.zip') as archive:
        for row in records:
            assert row['path'] not in paths, 'Duplicate manifest path'
            paths.add(row['path'])
            assert hashlib.sha256(archive.read(row['path'])).hexdigest() == row['sha256'], row['path']
            groups[row['group']].add(row['split'])
            hashes[row['sha256']].add(row['split'])
    assert all(len(v) == 1 for v in groups.values()), 'A group crosses splits'
    assert all(len(v) == 1 for v in hashes.values()), 'Identical image bytes cross splits'
    counts = collections.Counter((r['species'], r['split']) for r in records)
    assert counts == {('cat','train'):412,('cat','validation'):84,('cat','test'):81,('dog','train'):369,('dog','validation'):84,('dog','test'):78}, counts
    print('PASS: 1,108 image hashes; fixed splits; both model manifest identities.')

if __name__ == '__main__':
    main()
