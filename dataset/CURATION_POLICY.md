# PetVision v2 curation policy

This is an experimental photo-classification dataset, not a set of verified veterinary diagnoses. Source labels are retained or mapped to broader labels; visual review is for obvious content problems, not diagnosis. Higher accuracy is an objective to evaluate, not a property established by this cleaning process.

## Class mapping

- Original cat ringworm and fungal infection -> Fungal skin condition.
- Original dog fungal infection -> Fungal skin condition.
- Roboflow Ringworm -> cat Fungal skin condition; Scabies -> cat Scabies; Health -> cat Normal-looking skin.
- VetDerm ringworm/Fungal_infections -> dog Fungal skin condition; demodicosis -> dog Mange (broader category); Healthy -> dog Normal-looking skin.
- Flea Allergy, Dermatitis and Hypersensitivity are outside the current class definitions. They are excluded rather than reassigned to another diagnosis.
- Mendeley multispectral acquisition is excluded from the ordinary-photo model. Its original archive is preserved for future specialist work. A visible-light frame in this device series is not automatically treated as a phone photograph.

Normal-looking skin is a source-supported appearance category. It does not mean overall health, and the sources do not provide balanced normal dental, eye and ear examinations. Unsupported diseases and unrelated images remain outside the model's label set. Model confidence must not be described as a calibrated probability of disease.

## Deduplication and review

Decode images with Pillow, normalize EXIF orientation for pixel hashing, and compute perceptual hashes for eight orientations. Join identical pixels, old duplicate groups, Roboflow filename siblings, and perceptual matches within five bits. This is a conservative heuristic: similar images may be unnecessarily joined and some crops/augmentations may be missed. Unknown patient identity cannot be recovered reliably.

Exclude groups with conflicting mapped species or labels. Keep one representative of each remaining group, preferring the original dataset and higher resolution. To limit source imbalance and permit complete contact-sheet screening of the selected core, cap additional candidates at 100 groups per source and mapped class using stable hash order. Reserve remaining candidates outside the training ZIP; this is not a declaration that every reserved image is bad. Review all 1,624 selected representatives across 21 contact sheets for obvious human-only images, wrong species, specialist light channels, illustrations, screenshots with inadequate subject detail, and unusable photographs. Link additional related photographs manually. Exclude uncertain content without inventing a replacement diagnosis. This is contact-sheet content screening, not full-resolution or clinical verification of every image. No images are removed based on model predictions or to raise test scores.

## Evaluation limitations

Previously tested original images and their detected relatives must never move into training or validation. Old validation groups are also protected. Supplemental disease groups without a prior split are training-only: the retained original validation/test groups evaluate these disease categories. The new normal-looking category uses a 70/15/15 allocation of detected groups per species/source. The old test has already informed project decisions, so it is not a new blind evaluation. New normal-looking holdouts also have uncertain patient independence and source/style confounding. Compare per-class precision/recall and macro-F1 as well as accuracy; a broader fungal class and an added normal-looking class change the task, so v1 and v2 headline accuracy are not directly comparable.

The exported images are EXIF-oriented, converted to RGB JPEG at quality 95, with aspect ratio preserved and a maximum edge of 1,024 pixels. No synthetic training images are generated. Original image bytes and labels remain recoverable from the unchanged source archives via the provenance manifest.

## Source attribution and rights

- Original Pet_vision_DS copy: supplied by the user; upstream rights and diagnostic provenance not established.
- [Cat Skin Disease Classification, alvian](https://universe.roboflow.com/alvian-i1njf/cat-skin-disease-classification-b18ja), version 1. Publisher states CC BY 4.0. Export already resized/contrast-enhanced/augmented; those changes cannot be reversed.
- [VetDerm, shrayyyy](https://huggingface.co/datasets/shrayyyy/vet-derm-dataset). Publisher states Apache 2.0 and identifies a derivative of Dog's Skin Diseases Image Dataset. Individual image provenance is incomplete.
- [Mendeley dataset 5dbht54kw7, version 1](https://data.mendeley.com/datasets/5dbht54kw7/1). Publisher states CC BY 4.0. Not included in the training ZIP.

These are publisher declarations, not independently established ownership of scraped images. This mixed-source research package is not assigned a new blanket license. Preserve attribution; public redistribution of the original or uncertain-provenance images needs a separate rights review.
