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
