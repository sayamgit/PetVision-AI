# Evidence for the capstone review

This page addresses the six questions in the project guide's review. It distinguishes saved experimental results, implementation details, freshly executed software tests, and work not yet evaluated.

## 1. Dataset

The [dataset directory](../../dataset/README.md) contains the original `Pet_vision_DS.zip`, the exact `PetVision_dataset_v2.zip`, fixed training manifest, source attribution, checksums and a verification script. Original archive: 1,134 image files. Curated package: 1,108 retained images (781 training, 168 validation, 159 test). Cat totals: 412/84/81; dog totals: 369/84/78.

The team estimates about 15% of the original collection came from [smadive on Kaggle](https://www.kaggle.com/datasets/smadive/pet-disease-images); the rest was manually downloaded from websites. The curated package retains 849 original, 136 [Roboflow](https://universe.roboflow.com/alvian-i1njf/cat-skin-disease-classification-b18ja) and 123 [VetDerm](https://huggingface.co/datasets/shrayyyy/vet-derm-dataset) images. Individual URLs and rights for the original web downloads are incomplete; this is not a clinically verified or wholly team-owned image collection.

Run `python dataset/verify_dataset.py` from the repository root. Both archive hashes, all 1,108 retained-image hashes and the manifest identity in both model metadata files passed verification. Detected duplicate groups stay in one split, but unknown patient identity and earlier test exposure remain limitations.

## 2. Model training

The [original v2 Colab notebook](../../dataset/PetVision_Colab_Training_v2.ipynb) contains the training code and compressed fixed manifest. It has no saved execution outputs, so it is evidence of the training procedure, not a complete historical epoch log.

- Architecture: torchvision MobileNetV3-Small, pretrained `IMAGENET1K_V1` weights. Architecture paper: [Howard et al., Searching for MobileNetV3, ICCV 2019](https://arxiv.org/abs/1905.02244).
- Separate cat (6-class) and dog (7-class) classifiers. The feature extractor (`model.features`) is frozen; `model.classifier` is trained after replacing its final layer. This is classifier-head transfer learning, not end-to-end fine-tuning of the backbone.
- Images are fitted into 224 x 224 pixels with grey padding (128,128,128), converted to tensors and normalised with ImageNet mean and standard deviation. Training applies random horizontal flips.
- Adam optimiser, cross-entropy loss, batch size 16, learning rate 0.001. Base configuration seed 42; dog training adds 1000, giving effective seed 1042.
- At most 20 epochs; early stopping after 5 epochs without validation group-balanced macro-F1 improvement. The validation score selects the best checkpoint. This does not claim that both runs completed all 20 epochs.
- [Cat metadata](../../ml/artifacts/curated-v2/cat/model_metadata.json), [dog metadata](../../ml/artifacts/curated-v2/dog/model_metadata.json).

## 3. Model evaluation

The following values are recalculated from the saved `all_files` confusion matrices. They are not new inference runs. Rows are actual labels; columns are predicted labels. The diagonal sum divided by the number of test images gives accuracy. Precision = TP/(TP+FP), recall = TP/(TP+FN), and F1 is their harmonic mean. Macro-F1 averages class F1 values equally.

### Cat: 49/81 correct = 60.5%, macro-F1 0.604

| Class | Test images | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Dental Disease | 16 | 0.824 | 0.875 | 0.848 |
| Ear Mites | 11 | 0.556 | 0.455 | 0.500 |
| Eye Infection | 15 | 0.550 | 0.733 | 0.629 |
| Fungal skin condition | 18 | 0.300 | 0.167 | 0.214 |
| Normal-looking skin | 11 | 1.000 | 0.727 | 0.842 |
| Scabies | 10 | 0.471 | 0.800 | 0.593 |

Confusion matrix (class order as above):

```text
14  1  0  1  0  0
 1  5  2  3  0  0
 1  1 11  1  0  1
 1  2  6  3  0  6
 0  0  0  1  8  2
 0  0  1  1  0  8
```

### Dog: 55/78 correct = 70.5%, macro-F1 0.694

| Class | Test images | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| Dental Disease | 15 | 0.938 | 1.000 | 0.968 |
| Eye Infection | 10 | 0.900 | 0.900 | 0.900 |
| Fungal skin condition | 12 | 0.333 | 0.250 | 0.286 |
| Hot Spots | 10 | 0.750 | 0.600 | 0.667 |
| Mange | 12 | 0.476 | 0.833 | 0.606 |
| Normal-looking skin | 8 | 1.000 | 0.500 | 0.667 |
| Tick Infestation | 11 | 0.800 | 0.727 | 0.762 |

Confusion matrix (class order as above):

```text
15  0  0  0  0  0  0
 0  9  0  0  1  0  0
 0  1  3  0  7  0  1
 0  0  4  6  0  0  0
 0  0  1  1 10  0  0
 0  0  0  1  2  4  1
 1  0  1  0  1  0  8
```

Cat errors include 6 fungal images predicted as eye infection and 6 as scabies. Dog errors include 7 fungal images predicted as mange. This explains part of the overall error count. Image quality, label noise and visually similar classes are plausible factors but have not been isolated experimentally. Fungal recall is 3/18 for cats and 3/12 for dogs. An overall 70.5% score must not be described as reliable fungal-condition detection.

[Cat evaluation JSON](../../ml/artifacts/curated-v2/cat/test_metrics.json) and [dog evaluation JSON](../../ml/artifacts/curated-v2/dog/test_metrics.json) include the exact values and model hashes. Scores are experimental and do not establish clinical diagnostic accuracy. A displayed softmax score is not a calibrated disease probability.

## 4. AI agent

[gemini_engine.py](../../backend/pets/gemini_engine.py) contains the REST adapter, system prompt, JSON schema, request construction and response checks. The configured model is `gemini-3.1-flash-lite`, temperature 0.2, maximum output 1,200 tokens and request timeout 45 seconds.

`payload_for` supplies species, age, up to six recent Q/A exchanges and maintained reference notes, mainly selected by species. Photo follow-up adds a category and written observations; it does not send image bytes or the full pet record. There is no vector database, GraphRAG or live web retrieval. [reference_library.py](../../backend/pets/reference_library.py) and [practical_care.py](../../backend/pets/practical_care.py) show the maintained content and sources.

The system prompt constrains pet-care scope, requests useful follow-ups, includes urgency rules and forbids presenting image scores as a diagnosis. `parse_response` checks response types, lengths, urgency values and permitted source IDs and rejects certain URL/dose patterns. These checks do not prove factual accuracy or that a citation supports every claim. Provider failure invokes an explicitly labelled limited reference guide.

[test_gemini.py](../../backend/pets/test_gemini.py) checks consent, context handling, request schema, source IDs and failure handling with mocked responses. **No veterinarian-scored benchmark of agent factual accuracy or clinical reliability has been completed.** A future evaluation should use fixed cases with clinician ratings of factuality, urgency, citation support and harmful advice, plus repeated runs and provider-availability measurements. These are proposed evaluations, not reported results.

## 5. Source code and software testing

[Full test report](test-report-20261107.txt): 143 tests passed on 7 November 2026 in 65.670 seconds, exit code 0, no Django system-check issues. The report records the source commit and each test name. Test modules are under [backend/pets](../../backend/pets).

Reproduction (after installing the project dependencies):

```sh
python backend/manage.py test pets --noinput --verbosity 2
python dataset/verify_dataset.py
python tools/check_repository.py
```

These are different checks. Software tests do not measure the image model's diagnostic accuracy or Gemini's clinical accuracy. The QR browser regression runner is documented in [tools/qa/README.md](../../tools/qa/README.md); the 143 figure refers to the Django suite only. Tests use a separate SQLite test database and mocked provider responses. The hosted database is not touched.

## 6. Originality and existing applications

- [TTcare](https://ttcare.ai/) advertises AI photo checks, voice intake, health records and care plans.
- [TTcare Vet](https://ttcarevet.com/en) advertises image screening, consultation scribing and gait analysis for veterinary professionals.
- PetVision-AI's student contribution is its implemented workflow: reference-guided text conversation, two transparent image-classifier baselines, saved profiles, QR finder reports with explicit location consent, reminders and tested ownership checks. It is not a new foundation model or a claim that integrated pet-care AI is unprecedented.

Product descriptions were reviewed on 7 November 2026 and are qualitative, not an independent product performance benchmark. [Hwang et al. (2022)](https://doi.org/10.1007/s13273-022-00249-7) reports 70% validation accuracy for its best single fungal model and 87% for its combined fungal model. Both are relevant context, but their binary task, dataset and acquisition protocol differ from our seven-class dog test. These scores cannot establish that PetVision-AI outperforms the paper.
