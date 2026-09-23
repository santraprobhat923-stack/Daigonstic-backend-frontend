# Aarogyam

Single-repository diagnostic-centre workflow.

## Start
uvicorn backend.main:app --host 0.0.0.0 --port 8000

Open the server URL in Chrome.

## Workflow
Image upload → OCR → editable technician verification → generated PDF → immediate centre download → optional payment/WhatsApp automation.

WhatsApp OFF means no message is queued. WhatsApp ON + Due queues a payment request; Paid/verified payment releases the report and queues the final report message.

There is no patient registration, order prerequisite, patient portal, or patient login.

## Production environment
Copy .env.example to .env and set a strong SECRET_KEY. For Meta WhatsApp Cloud API set WHATSAPP_PROVIDER=meta, PUBLIC_BASE_URL, WHATSAPP_TOKEN, and WHATSAPP_PHONE_NUMBER_ID.

The default provider is mock, so the workflow can be tested without external WhatsApp credentials.

## Layout
- backend/main.py — API and workflow orchestration
- backend/models.py — database models
- backend/auth.py — centre authentication/session signing
- backend/services.py — OCR, PDF, notification and queue services
- backend/workers/whatsapp_worker.py — automatic WhatsApp queue worker
- frontend/index.html — shell
- frontend/css/app.css — mobile UI
- frontend/js/app.js — centre UI
- storage/ — persistent uploaded images, templates and reports

## Important
Use a persistent server volume for STORAGE_DIR and a production PostgreSQL DATABASE_URL before launch at scale.

# PROJECT MEMORY / HANDOVER — READ THIS FIRST

This section is the source of truth for future work. If a new ChatGPT conversation starts, inspect this README and the current GitHub tree before asking the owner to re-explain the project.

## Authoritative product workflow
IMAGE UPLOAD → OCR → TECHNICIAN VERIFICATION/EDIT → PDF GENERATION → CENTRE DOWNLOAD → PAYMENT STATE → AUTOMATIC WHATSAPP → RELEASE/DOWNLOAD NOTIFICATIONS

1. Centre staff uploads one or multiple analyzer/report images from Android/Chrome.
2. OCR extracts patient details and test results.
3. Technician edits and approves OCR data. No manual patient registration.
4. One credit is consumed for one generated report.
5. PDF is generated using the centre template when available and is permanently stored.
6. Centre can download the generated PDF immediately. Payment NEVER blocks centre download.
7. If WhatsApp is OFF, no WhatsApp message is sent.
8. If WhatsApp is ON and payment is Due/Pending, the system automatically queues a payment request containing the amount and centre UPI.
9. If payment is Paid, or later verified in the backend, the report becomes RELEASED and the final report delivery is automatically queued.
10. Patient has no portal, account, OTP, or manual login in the normal workflow.
11. Patient report access uses a secure tokenized URL. Patient download creates a centre notification.

## Never reintroduce
- Order → Billing → Report prerequisites.
- 'Create the patient order first' screens.
- Manual patient registration.
- Patient portal as the main workflow.
- Patient OTP/login.
- Manual WhatsApp sending in the normal flow.
- Payment blocking the centre's PDF download.
- Hidden billing/order dependencies.

## Current architecture
Single repository only.

backend/main.py = FastAPI API and workflow orchestration.
backend/config.py = environment settings.
backend/database.py = SQLAlchemy engine/session.
backend/models.py = Centre, Report, Notification, WAJob.
backend/auth.py = signed centre authentication/session token.
backend/services.py = OCR, hashing, PDF generation, notification and WhatsApp queue helpers.
backend/workers/whatsapp_worker.py = automatic WhatsApp queue worker.
frontend/index.html = application shell.
frontend/css/app.css = responsive/mobile styling.
frontend/js/app.js = centre application UI.
storage/centre_<id>/images = uploaded images.
storage/centre_<id>/reports = permanently stored generated PDFs.
storage/centre_<id>/template.pdf = centre custom template.

The obsolete monolithic backend/app.py has been removed. Do not recreate it.

## Authentication / tenant isolation
Centre APIs use a signed Bearer session token. The server derives the centre ID from the validated token. Do not trust a browser-supplied centre_id for authorization.
Every report, notification, setting, credit balance, template and WhatsApp job belongs to a centre.

## Current frontend UI direction — 22 Sep 2026
The centre-facing frontend now follows a more restrained modern LIMS visual language based on the diagnostic/laboratory references reviewed for this redesign. The direction is intentionally operational rather than a generic SaaS dashboard: light clinical workspace, strong information hierarchy, compact report tables, subtle borders, restrained blue accenting, clear status badges, and touch-friendly controls.

The redesign keeps the existing centre workflow and API connections intact. It does not reintroduce order prerequisites, patient registration, patient portals, OTP login, or payment blocking of centre downloads. The verification screen remains the most important working surface, while the dashboard, reports, delivery and settings pages provide supporting operations. Android Chrome remains a first-class target.

This is a presentation-layer refinement only. Backend workflow, database models, authentication, OCR, PDF generation, payment state and WhatsApp automation are not changed by the visual redesign.

## Current implementation

- Centre login and centre creation.
- Tenant-aware authenticated API.
- Multiple image upload.
- Tesseract OCR when available.
- Editable OCR verification.
- SHA-256 image hashing.
- Report PDF generation and permanent storage.
- Centre download before payment.
- PDF template upload and merge.
- Payment states.
- UPI setting.
- WhatsApp ON/OFF.
- Automatic WhatsApp job queue and worker.
- Mock WhatsApp provider.
- Meta WhatsApp Cloud API provider hook.
- Report search.
- Notification Center.
- Patient token access.
- Legacy SQLite migration protection.
- Mobile-friendly frontend.
- Professional responsive centre UI styling.
- Authenticated PDF download using a bearer-aware fetch flow.
- Frontend cache-busting for index/app assets.
- Startup loading state instead of an empty page.
- Frontend startup/error handling so JavaScript failures produce a visible error screen rather than a completely blank page.
- DOM access hardened to use explicit element lookups instead of relying on browser-created global variables from element IDs.
- Current frontend commits: f045f522d88df635bea93c4fb89bc5c042723e6e and e47de8551ebe5b6a7390d91129e01b16ec590151.

## Current test/deployment status — 22 Sep 2026
The project has been pulled into a fresh Android/Termux working directory and the FastAPI server has successfully reached the frontend.

Observed healthy requests:
- GET / → 200 OK
- GET /static/css/app.css → 200 OK / 304
- GET /static/js/app.js → 200 OK / 304

A favicon.ico 404 was observed. This is harmless and does not affect application functionality.

### Latest server-side issue and fix — 22 Sep 2026

Uvicorn was logging `RuntimeError: Response content longer than Content-Length` for `GET /` while returning 200 OK. The root route was using `FileResponse` for `frontend/index.html`; on the Android/Termux shared-storage environment this could produce a response-body/content-length mismatch.

The root route now reads `frontend/index.html` directly and returns it through FastAPI `HTMLResponse`. This is isolated to serving the frontend shell and does not change the diagnostic workflow, authentication, OCR, PDF, payment or WhatsApp logic.

After pulling the latest main branch, restart Uvicorn and refresh Chrome.

### Latest issue and fix
The browser displayed a completely blank page even though FastAPI was returning 200 OK. The frontend was patched directly in GitHub.

The fix:
1. Added cache-busting query strings to CSS and JavaScript assets.
2. Added a visible initial loading screen.
3. Hardened frontend startup with explicit DOM element lookups.
4. Hardened login, upload, verification, payment, reports, settings and search interactions against browser global-ID behavior.
5. Added visible startup/error handling instead of leaving an empty <main> area.
6. Preserved the existing backend/database and did NOT require deleting the database or centre account.

After pulling the latest main branch, restart:
uvicorn backend.main:app --host 0.0.0.0 --port 8000

Then refresh Chrome.

### Current centre account status
A centre account has already been created successfully through the Aarogyam UI. Do not instruct the owner to recreate the centre unless the database is intentionally reset.

## OCR progress
Patient credential extraction is working on the tested analyzer image.

Earlier thyroid test extraction was incomplete: Free T4 was detected while T3/TSH and values/units were incorrectly parsed. The OCR parser in backend/services.py was subsequently upgraded with broader laboratory-unit recognition, normal result-row parsing, table-like OCR parsing, cleanup and deduplication.

This parser still needs real-world validation against thyroid, CBC, stool and chemistry images. OCR remains draft data until technician verification.

## PDF/template progress
The centre can upload a blank PDF template in Settings. The template is stored under the centre's storage and generated reports are overlaid onto it.

The centre-side generated PDF download feature has been implemented:
- Generated report download uses the authenticated bearer token.
- Downloads do not require payment.
- Download filename is Aarogyam_Report_<id>.pdf.
- Reports with generated PDFs show a Download button in Reports.
- The post-generation screen shows Download Generated PDF.

Important: template coordinate placement is not yet considered production-final. Real centre templates must be tested to ensure body content stays inside the blank body area and never overlaps logos, headers or footers.

## Current known technical work remaining
1. Validate the latest frontend on Android Chrome after pulling the two frontend fixes.
2. Test full workflow with actual analyzer images.
3. Re-test thyroid extraction and confirm T3, TSH, Free T4, values and units.
4. Test CBC, stool and chemistry OCR.
5. Generate a report using a real centre PDF template and verify body placement.
6. Verify generated PDF download on Android Chrome.
7. Validate payment and automatic WhatsApp behavior with WhatsApp OFF and ON.
8. Test patient token release/download and centre notification.
9. Strengthen atomic credit deduction/idempotency before production.
10. Improve WhatsApp retry/backoff/dead-letter handling.
11. Configure PostgreSQL and persistent storage for production.
12. Perform production security review: file validation, rate limits, token expiry/revocation, tenant isolation and backups.
13. Validate Meta WhatsApp Cloud API delivery only after public HTTPS and valid credentials are configured.
14. Add the future Super Admin controls, including dynamic credit pricing.

## WhatsApp environment
Default: WHATSAPP_PROVIDER=mock.
For real Meta delivery set WHATSAPP_PROVIDER=meta, PUBLIC_BASE_URL=https://your-public-https-domain, WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID.
Real WhatsApp delivery is not considered live until Meta credentials and public HTTPS are configured and tested.

## PDF template rule
Templates may contain logo/header/footer/contact information. Generated body content must not overlap those areas. Current implementation merges a ReportLab overlay onto the uploaded PDF; real centre templates still require deployment testing and coordinate adjustment where necessary.

## OCR rule
OCR is only a draft. Technician verification is authoritative. Report formats vary (CBC, thyroid, stool, chemistry, etc.), so do not assume one fixed layout.

## Credits
1 credit = 1 report generation. Default configured price is ₹2.50/credit. Downloads do not consume credits. Future Super Admin must be able to change pricing dynamically.


## Centre Credits & Razorpay Recharge — 22 Sep 2026

The centre credit system is now implemented in the restarted `Daigonstic-backend-frontend` repository.

### Credit rules
- **1 credit = 1 generated report.**
- Default price: **₹2.50 per credit**.
- Centre PDF downloads do not consume credits.
- Credits are tenant-scoped to the centre.
- A credit is deducted only when technician verification generates the report PDF.
- Re-verifying an already generated report does not deduct another credit.
- Every recharge and report-credit usage is recorded in a credit transaction ledger.

### Recharge flow
Centre Admin → **Credits & Recharge** → choose credit quantity → Razorpay Checkout → UPI/payment method → server-side Razorpay signature verification → credits added automatically.

Preset packages:
- 100 credits
- 250 credits
- 500 credits
- 1,000 credits
- Custom quantity

The centre never enters a UTR for the Razorpay flow.

### Razorpay configuration
Set these server environment variables before testing live/test payments:

`RAZORPAY_KEY_ID`  
`RAZORPAY_KEY_SECRET`  
`RAZORPAY_WEBHOOK_SECRET`

The backend creates Razorpay orders and calculates the amount from the server-side `CREDIT_PRICE_INR`; the browser cannot choose the price.

The payment verification endpoint validates the Razorpay signature before adding credits. A Razorpay `payment.captured` webhook is also supported for asynchronous confirmation and idempotent recharge recording.

### Credit ledger
The backend stores:
- `credit_orders` — centre, Razorpay order, credit quantity, amount and payment status.
- `credit_transactions` — recharge and report-usage entries, including Razorpay payment ID where applicable.

The centre UI shows the current balance and recent transaction history.

### Current UI
A **Credits & Recharge** section is available in the desktop sidebar and mobile drawer. The dashboard credit KPI remains visible, and recharge packages open Razorpay Checkout.

## Production checklist
- Deploy on the actual server.
- Use persistent STORAGE_DIR.
- Use PostgreSQL for production.
- Use a strong random SECRET_KEY.
- Use public HTTPS for patient links.
- Configure Meta WhatsApp before claiming real delivery.
- Test CBC, thyroid, stool and other report images.
- Test real centre PDF templates and body placement.
- Test repeated/double submissions and credit safety.
- Test patient download notifications.
- Add/verify database and file backups.
- Perform a production security review: auth, tenant isolation, rate limits, file validation and token handling.

## Development rule
Whenever workflow, architecture, API, database, deployment or important implementation changes, update this README in the same change.

## Handover rule
If the owner says 'continue Aarogyam' in a new page, first read this README and inspect the actual GitHub repository state. Do NOT ask the owner to re-explain the whole workflow when it is already documented here.

## Mental model
Capture image → OCR → Verify → Generate PDF → Centre downloads immediately → Optional payment → Automatic WhatsApp delivery/release → Notifications.

## Premium modern SaaS visual direction — 22 Sep 2026

The centre-facing UI has now been visually moved toward the selected premium modern SaaS reference direction. This is a presentation-layer change only.

Design characteristics:
- premium SaaS-style spacing, rounded cards and softer elevation
- dark, compact navigation rail with a clear active state
- refined indigo primary accent and subtle gradients
- cleaner typography and stronger visual hierarchy
- modern KPI cards, tables, upload surface and verification cards
- polished login experience
- responsive Android/mobile bottom navigation retained
- existing API calls, routes, authentication and diagnostic workflow are unchanged

The selected visual direction should be treated as the current design baseline for future UI work. Do not replace it with a generic hospital/LIMS template unless explicitly requested.



## Light premium SaaS visual system — 22 Sep 2026
The frontend has been redesigned to follow the selected Reference C premium SaaS composition while using a light background. This is a structural visual-system redesign rather than a simple color change: light navigation rail, spacious SaaS cards, rounded surfaces, subtle borders/shadows, purple accent actions, KPI tiles, modern upload/review surfaces, and responsive mobile treatment. Existing frontend APIs and Aarogyam workflow are unchanged.


## Sidebar + dashboard visualization update — 22 Sep 2026
Desktop and mobile now use the same left-sidebar navigation model. On mobile the sidebar opens from a menu button as a slide-in drawer; the previous fixed footer navigation is removed. The dashboard now includes a premium activity graph, workflow-health visualization and live-status styling. This is presentation-only and does not alter APIs or the diagnostic workflow.


## Workspace bootstrap/cache fix — 22 Sep 2026
The browser application shell now uses a fresh frontend asset version and a resilient startup path. Local storage access is guarded, startup waits for DOM readiness when needed, and initialization errors surface through the existing workspace error screen instead of leaving the initial “Loading workspace…” shell stuck. No backend workflow or database data is changed.


## Frontend syntax bootstrap fix — 22 Sep 2026
The mobile/desktop sidebar navigation template had a missing JavaScript string terminator after the generated navigation markup. That syntax error prevented the entire app.js file from executing, so the browser stayed on “Loading workspace…” and never reached `/api/me`. The navigation template is now correctly terminated. No backend or database workflow changes were made.


## Mobile viewport containment fix — 22 Sep 2026
The Android/mobile workspace had horizontal page overflow, allowing the entire application to be dragged sideways into blank space. The frontend now explicitly contains horizontal overflow at the document/app level, constrains workspace/grid/card/chart widths, and collapses the technician verification five-column patient grid to one column on narrow screens. This is a presentation-only responsive fix; backend workflow and stored data are unchanged.


## Dark sidebar theme — 22 Sep 2026
The centre-facing navigation rail and mobile slide-in drawer now use a dark premium theme while the main workspace remains light. Navigation uses muted light text, a violet active state, subtle hover surfaces, and a dark mobile menu button. This is presentation-only; APIs, authentication, OCR, PDF, payment and WhatsApp workflow are unchanged.


## OCR extraction upgrade — 22 Sep 2026
The OCR service has been strengthened for real photographed analyzer slips. It now runs multiple Tesseract passes (PSM 6, 4 and 11) over grayscale/autocontrast/sharpened images, then merges the readings. Patient metadata parsing is line-anchored so the patient name is not allowed to consume Age/Sex/Phone/Patient-ID fields. Laboratory result parsing now recognizes common diagnostic units and irregular/table-style rows, while deduplicating repeated OCR readings. Test names and units are taken from the image rather than hard-coded to CBC/thyroid/stool/chemistry types. OCR remains draft data and technician verification remains authoritative.

## Upload/OCR progress messaging — 22 Sep 2026
The New Report upload surface now gives visible, human-readable progress while an analyzer slip is being processed: Ready to upload → Uploading slip → Creating report job → Reading analyzer slip with OCR → Checking extracted data → OCR complete / technician review. Duplicate images are detected against previously uploaded centre reports and are reported clearly instead of silently creating another report. If an upload succeeds but OCR itself fails, the UI keeps the report and explicitly tells the technician that OCR needs attention rather than showing a blank or generic failure.


## Fast OCR intake + Pending Verification queue — 22 Sep 2026

The upload path has been changed so the technician no longer waits for Tesseract OCR to finish before the upload request returns. Image hashing, duplicate detection, file storage and report-job creation happen in the request; OCR now runs in a background task and changes the report from `OCR_PROCESSING` to `OCR_REVIEW` when extraction is ready.

A new **Pending Verification** workspace entry lets staff upload multiple slips first and review them later from one queue. Processing jobs show live polling status; completed OCR jobs show a Review action that opens the existing editable technician verification screen. This does not change the authoritative workflow: OCR remains draft data and technician approval is still required before PDF generation.

The upload screen now returns to the queue after the report job is created instead of waiting for OCR. This is intended to make high-volume Android intake substantially more responsive while keeping the existing report/PDF/payment/WhatsApp workflow intact.

## WhatsApp automation hardening — 22 Sep 2026

The WhatsApp delivery path now follows the planned centre workflow end-to-end:

- **WhatsApp OFF:** no patient message is queued and centre PDF download remains available.
- **WhatsApp ON + payment Due:** a `PAYMENT_REQUEST` job is queued automatically with the patient amount and centre UPI ID.
- **Payment Paid / verified:** the report becomes `RELEASED` and a `FINAL_REPORT` job is queued automatically.
- The final Meta message is designed to deliver the generated PDF as a WhatsApp **document**, using the secure tokenized patient-report URL rather than exposing a local storage path.
- WhatsApp jobs are idempotent per report/message kind, so the same payment or final-report event does not create duplicate jobs.
- The worker now uses `PENDING → PROCESSING → SENT` and `RETRY → DEAD_LETTER` states with bounded retry delays and stores the last delivery error.
- Centre notifications are created for successful WhatsApp sends and permanently failed/dead-letter jobs.
- Existing reports and SQLite databases are migrated automatically with the new WhatsApp retry columns; no intentional database reset is required.

### Meta WhatsApp configuration

Local development continues to use:

`WHATSAPP_PROVIDER=mock`

For real Meta Cloud API delivery, configure:

`WHATSAPP_PROVIDER=meta`  
`PUBLIC_BASE_URL=https://your-public-https-domain`  
`WHATSAPP_TOKEN=...`  
`WHATSAPP_PHONE_NUMBER_ID=...`  
`WHATSAPP_PAYMENT_TEMPLATE=aarogyam_payment`  
`WHATSAPP_REPORT_TEMPLATE=aarogyam_report`  
`WHATSAPP_TEMPLATE_LANG=en_US`

The Meta templates must be created/approved in the WhatsApp Business account with parameters matching Aarogyam:
- payment template: amount + centre UPI in the body;
- report template: document header + patient name in the body.

The report template's document is fetched by Meta from the public HTTPS tokenized report URL. Therefore real delivery requires a publicly reachable HTTPS deployment and a valid Meta access token/phone-number ID. Localhost/Android LAN URLs are not valid for the real patient document delivery path.

The centre UI exposes the active provider and template names in **Centre Settings**, but secrets are never returned to the browser.

### Delivery rule

Payment is a **patient-release/delivery state**, not a PDF-generation prerequisite. Aarogyam continues to generate and make the centre PDF downloadable immediately after technician verification. WhatsApp automation operates after that point.

## Saved progress checkpoint — 22 Sep 2026

The current implementation checkpoint is preserved here for continuation.

### Completed in this phase
- Asynchronous OCR intake: upload requests return without waiting for Tesseract.
- **Pending Verification** queue added so centres can upload multiple slips and review OCR jobs later.
- Queue polling distinguishes processing jobs from OCR-ready jobs and opens the existing editable verification flow.
- Premium responsive centre UI, dark sidebar/drawer, dashboard visualizations and mobile overflow fixes are preserved.
- Root HTML serving was hardened for Android/Termux shared storage.
- Frontend startup/loading and JavaScript error handling were hardened to avoid blank/stuck workspace states.
- PDF generation remains independent of payment; centre download remains available immediately after verification.
- WhatsApp automation is implemented with mock provider by default.
- WhatsApp payment-request and final-report jobs are idempotent and processed by a background worker with retry/dead-letter states.
- Real Meta WhatsApp delivery support is wired behind environment configuration and requires public HTTPS plus valid Meta credentials/templates.
- README is the handover source of truth; future workflow/architecture/API/database/deployment/important implementation changes must be recorded here.

### Current testing checkpoint
The latest WhatsApp and Pending Verification changes have been committed to main, but the owner has not yet completed the fresh local pull/restart/test cycle after these latest changes.

Recommended next local startup:
cd /storage/emulated/0/diagnostic_backend
git pull origin main
uvicorn backend.main:app --host 0.0.0.0 --port 8000

Then test the workflow in this order:
1. Upload several analyzer images and confirm they return quickly.
2. Open **Pending Verification** and confirm jobs move from processing to OCR-ready.
3. Open each job, verify/edit patient details and test values, then generate the PDF.
4. Confirm the centre can download the PDF without payment.
5. With WhatsApp OFF, confirm no WhatsApp job is created.
6. With WhatsApp ON + UPI configured, confirm a Due report queues PAYMENT_REQUEST and the mock worker reaches SENT.
7. Mark/verify payment and confirm FINAL_REPORT is queued and reaches SENT in mock mode.
8. Confirm delivery notifications appear.
9. Only after the local workflow is stable, move the same build to the real server and configure Meta/public HTTPS.

### Important continuity rule
Do not reset the database, recreate the centre, or reintroduce order/billing prerequisites merely because a workflow screen is incomplete. Diagnose the actual API/frontend state first. The intended workflow remains:

**Capture image → OCR → Pending Verification → Technician Verify/Edit → Generate PDF → Centre Download → Optional Payment → Automatic WhatsApp Release/Delivery → Notifications.**


## Professional diagnostic PDF body — 23 Sep 2026

The PDF generation body has been redesigned to produce a professional diagnostic/laboratory report layout rather than a plain software data dump.

### Template responsibility
- The centre uploads a PDF template containing its own logo, header, branding, contact information, footer, doctor/signature and disclaimer.
- Aarogyam does not replace the centre branding.
- Aarogyam renders only the structured report body and overlays it onto the uploaded template.
- The body is intentionally kept inside a safe content area so it does not normally overlap the centre header/footer.

### Body structure
The generated body now supports:
- Professional patient-information block.
- Name, age/gender, patient ID, UHID, referred by, received on, reported on and phone when available.
- Department and report title.
- Bold section headers such as Physical Examination, Chemical Examination and Microscopical Examination.
- Consistently aligned test names, results and units.
- Automatic wrapping for long test names/results.
- Multiple report sections and variable diagnostic test types.
- Technician-editable section, test name, result and unit fields before PDF generation.

### OCR/verification support
OCR now attempts to extract additional patient credentials such as UHID, referred by, received date and reported date, plus report department/title and section information. These remain draft values until technician verification.

The technician verification screen now allows correction of all these fields and grouping of results into report sections. The final PDF is generated only from the verified data.

### Current PDF renderer
backend/report_renderer.py owns the professional body layout. backend/services.py passes the verified report data to the renderer. The uploaded centre template remains the visual branding layer.

### Important testing requirement
The renderer uses a generic A4 body coordinate area and therefore must be tested against real centre templates before production. Each centre's header/footer height and body-safe area can differ. A real Sunrise-style template should be uploaded and tested for:
1. No overlap with header/logo.
2. No overlap with footer/signature/disclaimer.
3. Correct patient-information alignment.
4. Correct section/result alignment.
5. Long result wrapping.
6. One-page and multi-page behaviour.

### Frontend cache
The centre frontend asset version was bumped after the PDF verification UI changes. After pulling the latest main branch, restart Uvicorn and refresh Chrome.

## Latest implementation checkpoint — 23 Sep 2026

Professional PDF body work is now committed on main. The intended flow remains:

**Capture image → OCR → Pending Verification → Technician Verify/Edit credentials + report sections → Generate professional PDF body → Overlay on centre template → Centre Download → Optional Payment → Automatic WhatsApp Release/Delivery → Notifications.**


## Android camera intake — 23 Sep 2026

The New Report intake now has a dedicated **Take Photo** camera action using the device rear camera, plus **Choose from Gallery**. Camera and gallery images are collected into one intake list before submission, allowing staff to take multiple photos one after another or select multiple existing images and then start the existing OCR upload flow once.

The camera input is reset after each capture so another photo can be taken immediately. Duplicate selections within the intake list are ignored, individual images can be removed before upload, and the Upload button remains disabled until at least one image is present. This is frontend-only and does not change the existing report/OCR API.

The frontend asset version was bumped after this fix. Pull main and refresh Chrome before testing.
