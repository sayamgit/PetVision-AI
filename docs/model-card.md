# Deployed image models: curated-v2

Separate MobileNet V3 Small classifiers are included for cats and dogs. Their existing weights, label order and preprocessing are unchanged. Startup verifies SHA-256 against the supplied evaluation records; no model downloads occur at request time.

| Model | Curated test images | Accuracy | Macro-F1 | Categories |
| --- | ---: | ---: | ---: | ---: |
| Cat | 81 | 60.5% | 0.604 | 6 |
| Dog | 78 | 70.5% | 0.694 | 7 |

These are small curated test results, not clinical validation. Fungal categories are particularly weak. Scores are uncalibrated and cannot be interpreted as the chance that an animal has a disease. A high score can be wrong; the highest category can be wrong for an ordinary pet portrait. The app marks split scores as inconclusive and offers a separate general-photo flow that does not classify diseases.

The normal-looking-skin category does not establish overall health. Symptoms and urgency require context regardless of the image score. Gemini does not alter model outputs or confirm infection subtypes.

The repository includes only the active weights, model metadata and evaluation JSON. Raw training images, downloaded candidate datasets, unpublished experiments and user uploads are excluded. The included artifacts are provided for the project's educational demonstration; this repository does not grant rights to third-party source imagery or assert a blanket dataset licence. A broader redistribution/commercial release requires a source-rights review.
