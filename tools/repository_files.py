"""Application release files and separately published review datasets."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
EXACT = (
    '.gitignore', '.dockerignore', '.github/workflows/checks.yml',
    'README.md', 'deploy/Dockerfile', 'render.yaml', 'deploy/environment.example',
    'requirements/app.txt', 'requirements/deploy.txt', 'requirements/inference.txt',
    'tools/windows/start-petvision.ps1', 'tools/windows/configure-gemini.ps1',
    'backend/manage.py', 'backend/serve.py', 'backend/check_gemini.py',
    'docs/app-setup.md', 'docs/deployment.md', 'docs/architecture.md',
    'docs/repository.md', 'docs/model-card.md', 'docs/care-planner.md',
    'docs/pet-chat.md', 'docs/verification-20261021.md', 'docs/supabase-setup.sql',
    'tools/repository_files.py', 'tools/check_repository.py', 'tools/package_release.py',
    'tools/qa/verify_container.py', 'tools/qa/check_container.py', 'tools/qa/README.md', 'tools/qa/verify_qr_flow.py', 'tools/qa/check_qr.cjs',
)
SOURCE = {'backend/config': {'.py'}, 'backend/pets': {'.py'},
          'backend/templates': {'.html'}, 'backend/static': {'.css', '.js', '.png', '.svg', '.webp', '.ico'}}


def release_files():
    paths = {ROOT/name for name in EXACT}
    for directory, suffixes in SOURCE.items():
        paths.update(path for path in (ROOT/directory).rglob('*')
                     if path.is_file() and path.suffix in suffixes
                     and '__pycache__' not in path.parts)
    for species in ('cat', 'dog'):
        folder = ROOT/'ml/artifacts/curated-v2'/species
        paths.update(folder/name for name in ('best_model.pt', 'model_metadata.json', 'test_metrics.json'))
        metrics = json.loads((folder/'test_metrics.json').read_text(encoding='utf-8'))
        with (folder/'best_model.pt').open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != metrics['model_sha256']:
                raise RuntimeError(f'{species}: model checksum mismatch')
    for path in paths:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError(f'Missing or unsafe release file: {path.relative_to(ROOT)}')
    return sorted(paths)


DATASET_FILES = (
    'Pet_vision_DS.zip', 'PetVision_dataset_v2.zip', 'README.md',
    'CURATION_POLICY.md', 'checksums.json', 'training_manifest.json',
    'verify_dataset.py', 'PetVision_Colab_Training_v2.ipynb',
)


def repository_files():
    """Include review datasets in Git, but keep them out of deployment packages."""
    paths = release_files()
    paths.extend(ROOT/name for name in ('docs/review-evidence/README.md', 'docs/review-evidence/test-report-20261107.txt'))
    for name in DATASET_FILES:
        path = ROOT/'dataset'/name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError(f'Missing or unsafe dataset file: {name}')
        paths.append(path)
    return sorted(paths)
