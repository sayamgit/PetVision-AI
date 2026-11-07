<p align="center"><img src="backend/static/pets/brand/petvision-companions.png" alt="PetVision cat and dog" width="140"></p>

# PetVision AI

**A little closer. Always.**

A Django application for cat and dog profiles, QR recovery, referenced care conversations and photo-based suggestions. Built as a college capstone with private pet records and owner-controlled sharing.

## What you can do

- **Keep pet profiles:** photos, care notes, medical details and veterinarian contacts.
- **Help a pet return home:** printable QR cards, missing status and private finder reports with optional, consented location sharing.
- **Ask care questions:** Gemini conversations grounded in a maintained veterinary reference catalog, with a limited local guide when the API is unavailable.
- **Explore a visible concern:** separate cat and dog image models, expandable alternative matches and inline symptom follow-ups. General photos have a separate flow.
- **Plan care:** weekly/monthly activity reports and calendar reminder exports for phone notifications.
- **Use a responsive interface:** light/dark themes, accessible motion controls and interactive cats on the sign-in page.

This is an educational project, **not a veterinary diagnostic service**. Image scores are uncalibrated model outputs. A normal-looking photo cannot establish health. See the [model card](docs/model-card.md).

## Repository

```text
backend/              Django application, templates, static assets and tests
ml/artifacts/         The two verified curated-v2 models and their evaluation metadata
docs/                 Setup, architecture, model limitations and deployment guides
tools/                Repository checks, release packaging and browser QA
.github/workflows/    Automated application and packaging checks
deploy/               Docker container and environment example
requirements/         Application, deployment and CPU inference dependencies
render.yaml           Free Render service configuration
```

Templates and frontend assets live inside `backend/`; this application does not require a separate frontend build. The [dataset folder](dataset/README.md) contains the original and curated image archives, source information and a verification script. Experiments, credentials, accounts and user-uploaded photos are excluded. See [what belongs in Git](docs/repository.md).

## Run locally

Use Python 3.12 and a virtual environment:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements/deploy.txt
python -m pip install -r requirements/inference.txt
python backend/manage.py migrate
python backend/manage.py runserver
```

Open http://127.0.0.1:8000/ and create an account. On Windows, `tools/windows/start-petvision.ps1` is also available. Gemini is optional: use `tools/windows/configure-gemini.ps1` or private environment variables `GEMINI_API_KEY` and `PETVISION_FREE_TIER_CONFIRMED=1`. Never commit the key.

## Verify

```bash
python backend/manage.py test pets
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py verify_release
python tools/check_repository.py
python tools/package_release.py
```

Application tests use synthetic data and mocked external responses. They do not spend Gemini quota. [QR browser checks](tools/qa/README.md) exercise location consent and finder reports separately.

## Hosting

The deployment target is **Render Free + Supabase Free**: PostgreSQL stores records, a private bucket stores photos, and Render serves the app and models. No paid resource is declared. Deployment still requires private configuration and live verification; a free plan is not an uptime or unlimited-storage guarantee.

Follow the [deployment guide](docs/deployment.md). A local Linux stress test passes under 512 MiB with both models, repeated large uploads and upload admission control. Live hosting and Supabase persistence still need verification. The local showcase database and its passwords are not shipped.

## Further reading

- [Architecture and privacy](docs/architecture.md)
- [Model evaluation and limitations](docs/model-card.md)
- [Reports and calendar reminders](docs/care-planner.md)
- [Care chat and fallback](docs/pet-chat.md)

## Review evidence

[Dataset sources, training method, model scores and test report](docs/review-evidence/README.md).
