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
