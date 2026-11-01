# Local application setup

Use Python 3.12 and a virtual environment. From the repository root:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements/deploy.txt
python -m pip install -r requirements/inference.txt
python backend/manage.py migrate
python backend/manage.py runserver
```

Open http://127.0.0.1:8000/ and create an account. Windows users may alternatively run `tools/windows/start-petvision.ps1` after installing the dependencies. The included CPU models work offline; optional Gemini replies require a private key. `tools/windows/configure-gemini.ps1` prompts locally and writes an ignored secret file. Never paste a key into source code.

Local SQLite, the generated local Django secret and private photos live under `backend/` and are excluded from Git. Static images are product assets, not private user uploads. Use [production deployment](deployment.md) for hosting; Django's development server is not the production entry point.

## Flows to review

1. Create a cat/dog profile and check its private photo and notes.
2. Choose exactly which fields the public QR card may show. Download its QR image, mark missing, submit a finder report and read it in the owner's inbox. Revoking a QR invalidates the old URL.
3. Open Care centre for an owned pet or a general animal. Ask a question, use the general-photo flow or explore a visible concern and its inline follow-up.
4. Open weekly/monthly reports and create a reminder. Import the calendar event into your calendar and enable notifications there.
5. Verify a second account cannot access the first account's private records.

`tel:` links open the device's calling application; browsers cannot silently bypass its call confirmation. Local QR codes pointing to 127.0.0.1 only work on the same computer. Phone scanning and geolocation require the final reachable HTTPS origin.

## Tests

```bash
python backend/manage.py test pets
python backend/manage.py makemigrations --check --dry-run
python backend/manage.py verify_release
```

See [browser QA](../tools/qa/README.md) for the isolated QR/location test. Tests use synthetic accounts; they do not need a real Gemini key.
