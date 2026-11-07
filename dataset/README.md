# PetVision-AI datasets

This directory contains the original team-curated collection and the exact curated-v2 image package associated with the deployed cat and dog models. These are educational image-classification datasets, not clinically verified diagnoses.

## Downloads and contents

| File | Contents | Size |
| --- | --- | --- |
| [Pet_vision_DS.zip](Pet_vision_DS.zip) | Original collection: 1,134 image files | 93,163,780 bytes |
| [PetVision_dataset_v2.zip](PetVision_dataset_v2.zip) | Curated collection: 1,108 retained images plus provenance files | 78,740,955 bytes |

The original archive was previously named `Pet_vision_DS-copy.zip`. Only the outer filename changed; the archive contents and checksum are unchanged. The curated ZIP is also unchanged. It contains images organised by `train`, `validation` and `test`, species, and category.

## Source attribution

1. **Original collection:** Mohammed Hashir Sayam Hussain reports that the team assembled it manually. Approximately 15% came from [smadive, Pet Disease images, Kaggle](https://www.kaggle.com/datasets/smadive/pet-disease-images). The remaining images were downloaded manually from websites, not photographed by the team. This proportion is a team estimate, not a verified per-file attribution. The retained manifest does not distinguish Kaggle files from other original web downloads.
2. **Cat supplement:** [alvian, Cat Skin Disease Classification, version 1, Roboflow Universe](https://universe.roboflow.com/alvian-i1njf/cat-skin-disease-classification-b18ja). Publisher states CC BY 4.0. Its export already includes resizing, contrast changes and augmentation.
3. **Dog supplement:** [shrayyyy, VetDerm, Hugging Face](https://huggingface.co/datasets/shrayyyy/vet-derm-dataset). Publisher states Apache-2.0 and identifies [youssefmohmmed, Dog's Skin Diseases Image Dataset, Kaggle](https://www.kaggle.com/datasets/youssefmohmmed/dogs-skin-diseases-image-dataset) as its upstream source.

The curated package retains 849 original, 136 Roboflow and 123 VetDerm images. The approximately 15% Kaggle estimate applies to the original collection, not to the final 1,108-image package. The Mendeley multispectral archive and later portrait/normal-gate experiments are **not** part of this curated-v2 dataset.

## Rights and provenance limitations

The team compiled third-party images and does not claim ownership of all photographs. Individual website URLs and redistribution permissions for the manually gathered original images have not been established. The Kaggle page's licence was not independently verified in this review. Supplement licences are publisher declarations, not independent proof of image ownership. This repository grants no new blanket licence over the mixed collection. Public availability is not permission for unrestricted reuse; check the original rights holders and applicable terms before reusing or redistributing images. Attribution above records what is currently known and does not replace missing permission.

## Fixed split

| Species | Train | Validation | Test | Total |
| --- | ---: | ---: | ---: | ---: |
| Cat | 412 | 84 | 81 | 577 |
| Dog | 369 | 84 | 78 | 531 |
| Total | 781 | 168 | 159 | 1,108 |

Cat classes: Dental Disease, Ear Mites, Eye Infection, Fungal skin condition, Normal-looking skin, Scabies.

Dog classes: Dental Disease, Eye Infection, Fungal skin condition, Hot Spots, Mange, Normal-looking skin, Tick Infestation.

See [CURATION_POLICY.md](CURATION_POLICY.md) for mappings, exclusion rules and split limitations. Images are EXIF-oriented RGB JPEGs, maximum edge 1,024 pixels. Detected duplicate/related groups stay within one split. Prior test and validation groups remain protected. Some test images had already informed development, so this is not a fresh blind evaluation. Patient identity and clinical labels are not independently verified. Normal-looking skin does not mean that an animal is healthy overall.

## Verification

From the repository root, run:

```sh
python dataset/verify_dataset.py
```

This dependency-free check verifies both archive hashes, all 1,108 retained-image hashes, split/group separation, and the canonical training manifest hash recorded in both deployed model metadata files. It does not retrain the models, validate image rights, or establish clinical correctness.

`training_manifest.json` is extracted from the original v2 Colab notebook without changing its content. It includes selected records, excluded candidates, labels, source paths, checksums and fixed splits. The shorter `image_manifest.json` inside the ZIP is not the same object as the full training manifest.

Canonical training manifest SHA-256: `b1bac2c9bf58742879cce38ddb3fa1dd8d5522ae6f49206389ef84f82dfa3788`.

Saved model results: [cat](../ml/artifacts/curated-v2/cat/test_metrics.json), [dog](../ml/artifacts/curated-v2/dog/test_metrics.json). Cat: 49/81 correct (60.5%); dog: 55/78 correct (70.5%). These are saved experimental scores, not a veterinary diagnostic accuracy claim.

Source/provenance review and archive verification: 6 November 2026. Docker's existing allowlist excludes this directory, so dataset archives are not included in the deployed application image.

## Training and review evidence

The [original v2 Colab notebook](PetVision_Colab_Training_v2.ipynb) contains the training procedure and fixed manifest. It has no stored execution outputs. See the [review evidence](../docs/review-evidence/README.md) for class-level metrics, confusion matrices, agent design and the full 143-test report.
