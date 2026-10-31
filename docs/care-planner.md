# Care reports and calendar reminders

Open **Care centre → your pet**. Weekly and monthly reports and reminders live beside the existing chat/photo tools.

## Reports

- Weekly means the past 7 calendar days including today; monthly means the past 30 days. Both run from midnight on the first day to generation time in Asia/Kolkata.
- Reports include answered owner messages (including follow-ups in older conversations), linked photo checks, saved questionnaires, reminders due and reminders marked done in the period.
- They are activity records, not diagnostic reports or measures of recovery. No saved records does not establish health. Deleted records and unlinked general-animal checks are excluded.
- Owner-only access is checked on HTML and text exports. Printing can save a PDF locally. Reports make no AI calls and store no extra photo/PDF copies. Each section displays at most 200 records and discloses truncation; counts include all matches.
- Downloaded reports contain private owner questions. Owners decide whom to share them with.

## Reminders outside PetVision

1. Add a one-time reminder with a future date/time, entered in India Standard Time. Use a veterinarian's instructions for medication/vaccination timing.
2. Click **Add to calendar**. PetVision downloads an `.ics` file; it does not connect to a calendar account.
3. Open/import the file in Apple Calendar, Google Calendar or another compatible calendar. For Google Calendar on desktop, use Settings → Import & export. Open the imported event.
4. Verify its date/time and add/check a notification, then save it. The file requests a display alert 30 minutes before, but calendar importers may handle alarms differently. Enable notifications for the calendar app on the phone and test a near-future event.

The calendar can alert while PetVision is closed. This depends on saving the event and enabling calendar/device notifications; PetVision cannot confirm delivery. There is no email service, background scheduler, push subscription or new paid API.

Calendar events contain pet name and reminder title, not private notes, contacts, medical details or photos. Choose a private calendar and avoid sensitive titles on shared calendars/lock screens. The event lasts 15 minutes as a calendar placeholder. UTC timestamps preserve the selected time across timezones. Files use stable event UIDs, UTF-8 line folding and escaped user text.

Events are independent copies, not a synced calendar. Marking done/removing a PetVision reminder does not change the phone event. Update/remove it there separately; do not repeatedly import it. Completed and past-due reminders cannot be exported. This first version supports one-time reminders; create another reminder for the next occurrence.

Up to 100 open reminders per pet; lists are paginated. Only small text/date records are added to the database. Existing image limits still apply; no unlimited-storage claim is made.

## Photo-chat availability

The server records a bounded failure identifier (usage limit, connection error, rejected request, authentication/access, model/provider error or unusable response), without logging provider bodies, keys or private request contents. HTTP 429 is described as a quota or rate limit; other failures are not labelled exhausted tokens. A synthetic free-tier request passed during this update; earlier generic failures cannot retrospectively be classified.

For supported photo topics, the reference fallback offers explicit choices about severe signs, onset and location/eating observations. Exact suggested answers continue locally without another Gemini call. Other typed wording in automatic mode tries Gemini again. Reference mode stays local. The guide preserves prior urgent advice, does not diagnose a subtype, and never modifies image scores. It is a limited guide, not a replacement language model or validated triage service.

References reviewed for ear guidance:
- https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center/health-information/feline-health-topics/feline-ear-disorders
- https://www.merckvetmanual.com/dog-owners/ear-disorders-of-dogs/ear-infections-and-otitis-externa-in-dogs
- https://vcahospitals.com/know-your-pet/instructions-for-ear-cleaning-in-cats
- Calendar import: https://support.google.com/calendar/answer/37118

## Storage and deployment

Local development stores records in SQLite and image bytes in private-media. Supabase deployment stores records in PostgreSQL and images in a private bucket, with authorized media views. New report/calendar exports are generated on demand. Model artifacts are separate; raw training archives need not be deployed. See [deployment](deployment.md) for configuration and persistence verification. Calendar reminders do not require PetVision to remain running after export.
