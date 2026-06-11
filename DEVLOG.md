# DEVLOG — Rangers Academia

Combined development log for **academia-api** (Django/Railway) and **academia-frontend** (React+Vite/Vercel).  
Commits from both repositories are merged chronologically and grouped by week.

---

## Week 1 — 2026-04-13 to 2026-04-19

### Milestone: Project Bootstrap

| Date | Repo | Author | Commit |
|------|------|--------|--------|
| 2026-04-15 | academia-api | camila | **Add gitignore** — Excluded secrets, venv, and build artifacts from version control |
| 2026-04-15 | academia-api | camila | **Initial commit — Academia API** — Django REST API scaffolded with core models (alumnos, grupos, pagos, pagadores) |

---

## May 13, 2026 — Invoice System Recovery & Platform Infrastructure

> Pre-commit working session (2.5 hrs). Changes from this session were bundled into the May 27 commits. No individual commits exist for this date.

### Milestone: Invoice Pipeline Fixed + Workflow Redesign

**System state at this point:** 12 alumnos · 14 pagadores · 11 grupos · CRM · Empresas · Placement test (120 questions) · Vocab game — all stable. Invoice generation was completely broken.

**5 bugs diagnosed and fixed:**

| File | Problem | Fix |
|------|---------|-----|
| `modules/documentos/invoice_service.py:251` | Syntax error — unescaped apostrophe in Mandela quote caused `SyntaxError: unterminated string literal`; module failed to import entirely | Removed apostrophe from the quote string |
| `modules/documentos/invoice_service.py` | PDF generation crashed on Windows with `CoInitialize error (-2147221008)` — `docx2pdf` uses Windows COM but it was never initialized | Wrapped conversion in `pythoncom.CoInitialize()` / `pythoncom.CoUninitialize()` |
| `Registro_Ingresos_2026.xlsx` | Excel log file corrupted at binary level (`Bad CRC-32` on internal ZIP/XML); every read/write degraded it further | Deleted the file; system recreates it fresh on next invoice |
| `modules/pagos/views.py` | `perform_create()` and `marcar_pagado()` both called `_auto_generate_doc()` — saving a payment auto-generated a document after a 4-second delay without user intent | Removed `_auto_generate_doc` calls entirely; generation is now user-initiated only |
| `modules/documentos/invoice_service.py` | Hard-coded strings lacked accents: `"ingles"` instead of `"inglés"`, `"TERMINOS"` instead of `"TÉRMINOS"` | Fixed strings with explicit `encoding='utf-8'` on file writes |

**Architecture decision — payment workflow redesigned:**

```
BEFORE:  Save Pago → auto-generates document (4s delay, user has no control)
AFTER:   Save Pago → instant
         Mark as paid (Cobrar) → instant
         Click "Factura" or "Recibo" → generates on demand
```

**New tooling created:**

| Script | Purpose |
|--------|---------|
| `diagnostico_api.py` | Ran 57 system checks; found all 9 issues in this session |
| `fix_invoice_all.py` | Applied CoInitialize fix, encoding fix, deleted corrupted Excel |
| `fix_pagos_views.py` | Stripped auto-generation from PagoViewSet |
| `ripple.py` | "Ripple Effect Analyzer" — system health checker that detects cascading failures before they happen; run `python ripple.py check` or `python ripple.py fix` |

---

## Week 7 — 2026-05-25 to 2026-05-31

### Milestone: Full-Stack Launch + PDF Invoicing + Railway/Vercel Deployment

| Date | Repo | Author | Commit |
|------|------|--------|--------|
| 2026-05-27 | academia-api | camila | **Add CRM/empresas/placement_test modules, invoice numbering, and module fixes** — Extended the API with CRM contacts, company tracking, placement tests, and sequential invoice numbering |
| 2026-05-27 | academia-api | camila | **Add Railway deployment config and production settings** — Added `railway.toml`, production environment settings, and static/media configuration for Railway |
| 2026-05-27 | academia-frontend | camila | **Initial commit — React+Vite frontend for academia management system** — Full SPA scaffolded with React Router, Axios, and JWT auth |
| 2026-05-27 | academia-frontend | camila | **Guard s.registros against null in AsistenciaPage history render** — Fixed crash when attendance record has no registros array |
| 2026-05-27 | academia-frontend | camila | **Rebuild PagosPage with inline create form and full payment list** — Replaced placeholder with functional payments page: create, list, and filter pagos |
| 2026-05-27 | academia-frontend | camila | **Rebuild AlumnosPage with improved cards, modal UX, and delete confirmation** — Student cards polished; add/edit modal and two-step delete guard added |
| 2026-05-27 | academia-frontend | camila | **Rebuild GruposPage with color accents, schedule chips, and delete modal** — Group list redesigned with color-coded cards and schedule tag chips |
| 2026-05-27 | academia-frontend | camila | **Rebuild PagadoresPage with proper delete modal and polished UX** — Payer list now has consistent card layout, edit flow, and delete confirmation |
| 2026-05-27 | academia-frontend | camila | **Rebuild DashboardPage with KPI cards, pending payments, and birthdays** — Dashboard rebuilt with revenue summary, pending cobros, and upcoming birthday list |
| 2026-05-27 | academia-frontend | camila | **Rebuild CRMPage with edit, delete, interaction logging, and search** — CRM rebuilt from scratch: search bar, interaction history, and full CRUD |
| 2026-05-27 | academia-frontend | camila | **Rebuild remaining pages: Cumpleanos, Documentos, Pendientes, Config, Empresas** — All secondary pages rebuilt with consistent layout and live data |
| 2026-05-27 | academia-frontend | camila | **Add WhatsApp button to student cards linking to pagador's phone** — Tapping the WA icon opens a pre-filled WhatsApp chat to the student's payer |
| 2026-05-27 | academia-frontend | camila | **Add vercel.json for SPA routing** — Configured catch-all rewrite so React Router works on Vercel without 404s on refresh |
| 2026-05-28 | academia-api | camila | **Fix .env: remove corrupted settings.py content and PostgreSQL DATABASE_URL** — Cleaned up .env file that had been accidentally polluted with raw settings |
| 2026-05-28 | academia-api | camila | **Replace docx/local-disk invoices with ReportLab PDF + Google Drive** — Dropped python-docx and local storage; invoices now generated as PDF with ReportLab and uploaded to Drive |
| 2026-05-28 | academia-api | camila | **Auto-create 'Rangers Academy Facturas' Drive folder; add credentials to gitignore** — Drive folder is created on first run; service account JSON excluded from repo |
| 2026-05-28 | academia-api | camila | **Add Google Drive invoice storage with ReportLab PDF generation** — PDFs are signed, uploaded, and a shareable Drive link stored on the Pago record |
| 2026-05-28 | academia-api | camila | **Increase logo size and improve PDF layout spacing** — Logo scaled up and section spacing tightened for a cleaner invoice look |
| 2026-05-28 | academia-api | camila | **Support GOOGLE_TOKEN_JSON env var for Railway deployment** — Service account credentials now read from env var so no JSON file is needed on Railway |
| 2026-05-28 | academia-frontend | camila | **Show error feedback on Cobrar button failure in PendientesPage** — Button now shows a red error message instead of silently failing when the API call fails |
| 2026-05-29 | academia-api | camila | **Add render.yaml with correct start and build commands** — Alternative Render.com deployment config added alongside the Railway setup |

---

## Week 8 — 2026-06-01 to 2026-06-07

### Milestone: Production Stabilization + Games + Email/WhatsApp Contact

| Date | Repo | Author | Commit |
|------|------|--------|--------|
| 2026-06-02 | academia-api | camila | **Fix CORS, CSRF trusted origins, and Django 6.0 STORAGES config for Railway** — Corrected allowed origins list and migrated deprecated `DEFAULT_FILE_STORAGE` to new `STORAGES` dict |
| 2026-06-02 | academia-frontend | camila | **Fix VITE_API_URL usage in refresh token interceptor** — Axios interceptor was falling back to localhost; now correctly reads `import.meta.env.VITE_API_URL` |
| 2026-06-03 | academia-api | camila | **Fix invoice numbering system — sync Pago.num_doc with generated PDFs** — Invoice serial number on the Pago model now always matches the number embedded in the PDF |
| 2026-06-03 | academia-api | camila | **Add email and WhatsApp contact endpoints for alumnos and pagadores** — New `/contactar/` endpoints expose email address and WhatsApp link for students and payers |
| 2026-06-03 | academia-frontend | camila | **Add Flashcard and Memory Match games** — Two interactive learning games added to the student-facing section |
| 2026-06-03 | academia-frontend | camila | **Add email buttons, Word Scramble game, fix dashboard** — Email contact buttons added throughout; Word Scramble game added; dashboard KPI calculation fixed |
| 2026-06-04 | academia-api | camila | **Backfill invoices for Pagos 22 and 23** — Management command run to generate missing PDFs for two payments that pre-dated the auto-invoice feature |
| 2026-06-04 | academia-api | camila | **Auto-generate invoice PDF on payment creation** — `post_save` signal now triggers PDF generation and Drive upload every time a Pago is created |
| 2026-06-04 | academia-api | camila | **Test and clean up auto-invoice smoke test (pagos 25-26)** — Smoke test script for the auto-invoice signal cleaned up and removed from the codebase |
| 2026-06-04 | academia-api | camila | **Update password for Academia2024 user** — Admin password rotated for the shared Academia2024 account |
| 2026-06-04 | academia-frontend | camila | **Pin Node >=20 for Vite 8 compatibility on Vercel** — Added `engines.node` constraint to `package.json` so Vercel picks Node 20 and Vite 8 builds correctly |

---

## Week 9 — 2026-06-08 to 2026-06-14

### Milestone: Payment Email Notifications

| Date | Repo | Author | Commit |
|------|------|--------|--------|
| 2026-06-11 | academia-api | camila | **Fix recibo prefix (REC→RE), add email notification on payment creation** — Receipt serial corrected from `REC-` to `RE-`; payer now receives an email confirmation with the invoice PDF link when a payment is recorded |

---

## Summary of Major Milestones

| Date | Milestone |
|------|-----------|
| 2026-04-15 | Academia API initial commit |
| 2026-05-13 | Invoice pipeline restored (5 bugs fixed); payment/document workflow separated; `ripple.py` diagnostic tool created |
| 2026-05-27 | Frontend launched; all core pages rebuilt; Railway + Vercel deployments live |
| 2026-05-28 | PDF invoice generation via ReportLab + Google Drive storage |
| 2026-06-03 | Contact endpoints (email/WhatsApp) + learning games added |
| 2026-06-04 | Auto-invoice on payment creation (post_save signal) |
| 2026-06-11 | Email notification to payer on every new payment |
