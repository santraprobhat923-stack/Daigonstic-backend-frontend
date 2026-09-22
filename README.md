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