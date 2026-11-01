# QR browser regression check

Run `python tools/qa/verify_qr_flow.py` from a checkout with the Django dependencies,
Node.js, Playwright, and its Chromium browser available. The runner uses a temporary
SQLite database, private media directory, secret and test owner; it never changes the
local pet records. It starts a disposable localhost server and removes the fixture
after the test. No real GPS coordinates or Gemini requests are used.

Optional environment overrides: `NODE_BINARY`, `PLAYWRIGHT_MODULE` (module path),
`BROWSER_EXECUTABLE` (for an installed Edge/Chrome), `QR_CHECK_SCREENSHOT` (output path).
The Node/browser tools are test dependencies only, not deployment dependencies.

This checks consented location persistence and the owner inbox, no automatic location
request, permission denial, stale-location clearing on failed retry, timeout/unavailable
errors, pending submission, cancellation and late callbacks, insecure/unsupported
contexts, public privacy, and QR PNG generation. Physical phone scanning, actual device
permission prompts and the final public HTTPS origin still need a deployment smoke test.


## Linux container memory check

```bash
docker build -f deploy/Dockerfile -t petvision:release .
python tools/qa/verify_container.py
```

Override the CLI location using `--docker` or `DOCKER_BINARY`, and the image tag using
`--image`. The test runs with 512 MiB RAM, no swap and no network. It uses temporary
accounts, a temporary SQLite database and generated photos inside the container.
No host media/database/secret directory is mounted. The container is removed afterward.

It loads both original models, submits small and 12 MP photos through Django's upload
view, repeats large uploads without forced test-side garbage collection, and checks
that four simultaneous uploads produce one completion and three retry responses.
It reports cgroup memory and Docker's OOM status. Linux may reclaim file-cache pages
at the limit; a successful run is not a guarantee for all traffic or remote services.
Supabase connectivity/persistence and final-host behavior still require a live check.
