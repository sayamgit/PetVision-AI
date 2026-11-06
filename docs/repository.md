# Repository boundaries

The GitHub repository contains application source, tests, templates, runtime graphics, active models, deployment files, documentation and QA tools. The `dataset/` directory contains the two review archives and their source and verification records. Dataset archives are excluded from Docker builds and application release ZIPs.

Unused local research was moved to a separate `PetVision-Archive` folder beside the project: `Normal/`, `TRAIN_THIS/`, `PetVision-extra-datasets/`, raw archives, notebooks, old manifests, ML experiments and historical review documents. The archive retains original relative paths and a `MOVE-MANIFEST.json` for restoration. The active project keeps its local database, private media and secrets; these remain ignored by Git.

Never add `.env.gemini`, other secret files, SQLite databases, uploaded/private photos, account exports, backups, caches or collected static output. Only the two curated-v2 model exports are admitted under `ml/artifacts/`.

`tools/check_repository.py` checks the staged/tracked file list against an explicit allowlist, scans common credential patterns without printing matches and rejects oversized files. It cannot prove that every possible secret is absent; review the staged diff before publishing. `tools/package_release.py` uses the application-only allowlist and verifies model hashes. The two named dataset ZIPs have a separate 100 MiB repository limit; other files retain the 25 MiB limit. Run `python dataset/verify_dataset.py` to verify the dataset content.

New application files must be in the documented source directories. New documentation or root files should be explicitly added to both the allowlist and `.gitignore` exceptions.
