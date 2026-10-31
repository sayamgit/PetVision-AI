> Historical verification record. The repository cleanup on 1 November 2026 added Supabase persistence configuration; live cloud validation is still pending. See [deployment](deployment.md).

# PetVision verification — 21 October 2026

The local application is ready for another owner review. It is not yet signed off for
public deployment. No hosting, paid service or public upload was created during this pass.

## Passed

- All 132 Django tests, including 18 recovery/QR tests. Migration drift check clean;
  no Django system-check errors; installed Python dependencies consistent.
- Both original curated-v2 model hashes verified. No retraining or model replacement.
- QR browser flow with a temporary database: simulated consented coordinates reached
  the owner inbox; no location was stored for the denied-permission report. Twelve
  browser checks cover consent, privacy, failure/retry, timeout, cancellation, late
  callbacks, unsupported/insecure contexts, and QR PNG generation. No browser JS errors.
- Backend recovery checks include missing/reunited status, report read status, revoked
  QR links, account isolation, CSRF, rate limits, invalid coordinates and independent
  opt-in sharing of public profile, photo, medical and contact details.
- Login browser checks: opening wall jump, walking left/right, click jump, username
  response, password paw cover, successful sign-in/sign-out, reduced motion/manual play,
  light/dark transparent login box, and mobile overflow. All five cover poses inspected.
- Isolated production configuration behind an actual local TLS proxy: registration and
  secure cookies; pet profile creation; care hub; weekly/monthly reports; calendar alarm;
  private notes and photo access; general photo checks; conversation handoff; actual
  cat/dog CPU inference with original weights; hashed static assets; mobile layout.
  Styles, brand images and cat assets loaded over HTTPS. This resolves the earlier
  unstyled screenshot from a simulated-HTTPS-over-HTTP test. Pipeline execution is not
  a clinical accuracy evaluation.

## Fixes in this pass

- Starting a new GPS request now clears old coordinates and sharing consent. A failed
  retry cannot accidentally submit a previously captured location.
- Pending GPS requests block submission until resolved or cleared. Clearing invalidates
  late callbacks. Permission denial, timeout, unsupported browser and insecure-page
  messages give the finder a landmark-only fallback.
- Corrected face-covering cat artwork, removed adjacent sprite fragments, and retained
  smooth walking/jump/pose transitions. Only the login box uses the requested glass style.
- Reusable isolated QR browser checks are saved in `tools/qa/`.

## Still required before deployment sign-off

- Live Gemini failed this pass: first a service error, then a connection failure. The
  diagnostic did not establish quota exhaustion. Offline fallback tests pass, but the
  external AI connection must be verified again; no paid fallback was enabled.
- Choose and configure a genuinely free host with persistent database and private
  photo storage. Current disk-based deployment is not suitable for an ephemeral host
  without adapting persistence. Test storage across a real-host restart.
- Scan a newly generated QR code on a separate phone using the final public HTTPS
  hostname. Test real location permission allow/deny, report delivery and call links.
  A QR containing 127.0.0.1 refers to the scanning phone, not this development computer.
- Phone call buttons hand off to the device's dialer; no actual call was placed.
  Finder reports currently appear in the owner dashboard, not an email/push notification.
- Linux container build remains untested. Production's two HSTS subdomain/preload
  warnings are deliberate until the domain and subdomain ownership are decided.

## Proposed Lost & Found page (not implemented)

An opt-in nearby feed with Missing, Found and Reunited states, neighborhood/city filters,
and report-to-owner actions would complement QR recovery. Publish approximate areas,
not precise home addresses or finder GPS coordinates. Retire missing listings when a
pet is reunited. A simple area filter can be a first version without paid map services.
