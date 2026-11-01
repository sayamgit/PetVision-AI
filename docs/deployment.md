# Deploy PetVision on Render and Supabase

Target: one Docker web service on Render Free, Supabase Free PostgreSQL and a private Supabase Storage bucket. No paid Render database or persistent disk is used. Keep one instance. Free plans have quotas and sleep/pause behavior; they are suitable for a supervised capstone pilot, not guaranteed always-on hosting.

## 1. Prepare Supabase

Confirm the account, organization, project and region. Singapore matches the proposed Render region; choose deliberately before deployment.

1. Leave the Data API disabled. Run [supabase-setup.sql](supabase-setup.sql) in the project's SQL Editor. This creates the private `petvision` schema for Django migrations.
2. Open **Connect**, select the **Session pooler** (IPv4, normally port 5432), and take the exact host, database and username from that project. Set the database password privately as `PETVISION_DB_PASSWORD`; separate fields avoid connection-string password encoding errors.
3. Create a **private** bucket named `petvision-photos` in Storage. Never enable public access.
4. In Storage S3 configuration, generate server-only S3 credentials. Copy the exact endpoint and region shown there into private environment settings. These are S3 keys, not the public/anonymous API key.
5. Keep credentials out of chat, screenshots, Git and build arguments. S3 keys bypass bucket RLS and must remain server-side.

Database connections require TLS. Supplying the downloaded Supabase CA via `PETVISION_DB_SSL_ROOT_CERT` enables hostname/certificate verification (`verify-full`); without it the driver uses `require` encryption.

## 2. Create the Render service

Connect the confirmed GitHub repository using a Blueprint and its `render.yaml`, or create a Docker Web Service manually. Choose **Free** and Singapore. Do not enable a paid disk or Render database. The Blueprint explicitly selects Free and leaves automatic deployments off.

Set the values in [deploy/environment.example](../deploy/environment.example) using Render's environment settings. Set `PETVISION_PUBLIC_BASE_URL` to the assigned HTTPS service origin and `PETVISION_ALLOWED_HOSTS` to that hostname plus `localhost,127.0.0.1`. Set `PETVISION_SECRET_KEY` to a random, stable value of at least 50 characters, generated locally with `secrets.token_urlsafe(64)`. The Blueprint prompts for it; Render's default generated value is shorter than this application's validation requires.

`PETVISION_STORAGE_MODE=supabase` is mandatory on Render. Production refuses a disk configuration there. Startup checks models, runs migrations and collects static assets before Waitress starts. Render terminates HTTPS; wildcard proxy trust is appropriate only behind that managed proxy, never on a directly exposed listener.

Gemini is optional. Set its key privately and confirm the free-tier project. No paid fallback is configured. Do not copy the local showcase account/database into the public app; create a fresh account and upload only the intended photos.

## 3. Verify before sharing

- Build with `docker build -f deploy/Dockerfile -t petvision:release .` and measure peak memory with both models and maximum-size uploads. Windows measurements alone do not verify Render's 512 MB limit. Do not declare the free deployment ready if it restarts or runs out of memory.
- Test signup/login, ownership isolation, private photos, QR sharing/revocation, both species' predictions, general photo checks, Gemini/fallback, reports and calendar export over the final HTTPS URL.
- Restart the service and verify the same test record and photo persist in Supabase.
- Scan a newly generated public QR code from a phone. Verify permission denial, optional consented location and the owner's finder inbox. Old localhost QR codes cannot reach the hosted app.
- Check logs without printing secrets. Monitor memory, database, storage and egress quotas. Delete unused checks through the app; back up records and files together.

## Local persistent-disk alternative

For a host with an actual durable volume, use `PETVISION_STORAGE_MODE=disk`, mount `/data`, set `PETVISION_DATA_DIR=/data`, and grant UID 10001 access. This is not Render Free. The same deploy/Dockerfile supports both modes.

## Limits

Free hosting may sleep or pause. No automated email/push reminders or password-reset email are configured. Calendar notifications require importing the reminder and enabling calendar alerts. Model results are not diagnoses. Free cloud services and third-party Gemini availability have no availability guarantee here.

Official setup references:
- [Render Free](https://render.com/docs/free)
- [Render Blueprints](https://render.com/docs/blueprint-spec)
- [Supabase database connections](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication)
- [Django storage configuration](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html)

Photo uploads are admitted one at a time per process to keep large image decoding within the free instance memory budget. A simultaneous upload receives HTTP 503 with a retry message and Retry-After; other page requests remain available.
