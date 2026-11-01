# Care conversations

Care centre offers conversations for an owned pet or another cat/dog. Gemini generates natural-language replies using the maintained reference notes and disclosed recent conversation context. It has no live web browsing and does not inspect the photo itself. Photo follow-ups use the selected uncertain category and the user's reported symptoms; they do not confirm an infection subtype or alter model scores.

## Configure Gemini

For local use, run `tools/windows/configure-gemini.ps1` and enter the key in its hidden prompt. The ignored `.env.gemini` stays on this computer. For hosting, set `GEMINI_API_KEY` and `PETVISION_FREE_TIER_CONFIRMED=1` privately in the host's environment. Keep billing disabled if only free use is intended. The app cannot verify billing from a key and never enables a paid fallback.

API availability and usage limits depend on the provider project/model. The app distinguishes a quota/rate-limit response from connection, authentication or service errors. An unavailable response does not by itself establish that daily quota is exhausted. A configured key is not proof of a successful live connection.

## Local fallback

The local guide matches supported wording against original short summaries and follows a finite conversation state machine. It uses the same application's database and does not require an external model or GPU. It cannot understand every question or follow-up. Unsupported input receives a limited response rather than an invented answer. Supported practical care steps and urgent signs are drawn from the reference catalog.

## Privacy and limits

The introductory disclosure explains the question, recent exchanges and species/age sent to Gemini; avoid personal/confidential details. Chats and photo discussions are private to their owner and are never shown on public QR cards. Suggested replies fill the message box; the user submits them. Accounts may delete conversations through the app.

Neither model output nor reference retrieval is clinical validation. The app does not prescribe medicines or medication doses, and missed emergency wording does not establish safety. References should be reviewed when guidance changes.

## Maintenance and tests

Reference summaries live in `backend/pets/reference_library.py`, `practical_care.py` and `photo_reference.py`. Keep summaries original, cite the supporting source and update the checked date. Tests cover context, fallback, owner isolation, API failure handling, prompt data, urgent wording and provider response validation. Run `python backend/manage.py test pets` without making a live API request.
