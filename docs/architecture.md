# Architecture

Browser → HTTPS proxy → one Waitress process → Django.

- Django handles accounts, authorization, pet records, QR finder reports, care history and reminders.
- Templates, CSS, JavaScript and local animation assets are served from the same application; WhiteNoise serves collected static assets.
- Production remote mode stores database records in Supabase PostgreSQL's `petvision` schema and photos in a private S3-compatible bucket. Records contain object names, not image blobs.
- Photo endpoints check ownership or the specific public QR sharing permission before opening a file. Direct object-store URLs are not exposed by the storage backend.
- Local development uses SQLite and private-media. These files are ignored by Git and are not part of deployment.
- The original curated-v2 CPU models load lazily. Model outputs remain separate from Gemini explanations. General checks do not invoke the disease classifier.
- Gemini receives the disclosed question/context and maintained reference summaries. Local fallback is limited; it is not an equivalent conversational model or live web search.
- Calendar exports transfer reminder responsibility to the user's calendar. There is no background push/email service.

One process is required because throttling and model caches are process-local. Uploaded photos are limited to 2 MB / 12 million pixels, sanitized and served privately. Free-host memory and storage limits still apply.

Photo uploads are admitted one at a time per process to keep large image decoding within the free instance memory budget. A simultaneous upload receives HTTP 503 with a retry message and Retry-After; other page requests remain available.
