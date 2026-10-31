# Repository boundaries

The GitHub repository contains the application source and tests, templates, runtime graphics, active model artifacts, deployment configuration, focused documentation and QA tools.

Unused local research was moved to a separate `PetVision-Archive` folder beside the project: `Normal/`, `TRAIN_THIS/`, `PetVision-extra-datasets/`, raw archives, notebooks, old manifests, ML experiments and historical review documents. The archive retains original relative paths and a `MOVE-MANIFEST.json` for restoration. The active project keeps its local database, private media and secrets; these remain ignored by Git.

Never add `.env.gemini`, other secret files, SQLite databases, uploaded/private photos, account exports, backups, caches or collected static output. Only the two curated-v2 model exports are admitted under `ml/artifacts/`.

`tools/check_repository.py` checks the staged/tracked file list against an explicit allowlist, scans common credential patterns without printing matches and rejects oversized files. It cannot prove that every possible secret is absent; review the staged diff before publishing. `tools/package_release.py` uses the same allowlist and verifies model hashes.

New application files must be in the documented source directories. New documentation or root files should be explicitly added to both the allowlist and `.gitignore` exceptions.
