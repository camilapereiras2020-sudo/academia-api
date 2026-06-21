# DEVLOG — Rangers Academia

Combined development log for **academia-api** (Django/Railway) and **academia-frontend** (React+Vite/Vercel).  
Commits from both repositories are merged chronologically and grouped by session.

---

## Milestones

| Date | Milestone |
|------|-----------|
| 2026-04-15 | Academia API initial commit — Django REST API bootstrapped, Docker → SQLite migration, GitHub repo initialized |
| 2026-04-26 | Passive income brainstorm; Cambridge PDF product concept identified |
| 2026-05-13 | Invoice pipeline restored (5 bugs fixed); payment/document workflow separated; `ripple.py` diagnostic tool created |
| 2026-05-27 | Frontend launched; all core pages rebuilt; Railway + Vercel deployments live |
| 2026-05-28 | PDF invoice generation via ReportLab + Google Drive storage |
| 2026-06-03 | Contact endpoints (email/WhatsApp) + learning games added |
| 2026-06-04 | Auto-invoice on payment creation (post_save signal) |
| 2026-06-10 | Deployment day confirmed live; Claude Code CLI installed; custom domain purchased |
| 2026-06-11 | Payment dashboard prototype; WhatsApp button; invoice logic; email notification on payment creation |
| 2026-06-15 | Tech briefing session; social media strategy; WhatsApp templates; file cleanup script; worksheet organizer; WA Business glitch |
| 2026-06-17 | Adult programme built; FUNDAE calculator; Duet Display setup; screen sharing for teaching |

---

## April 14–15, 2026 — Initial Setup

### Milestone: Project Bootstrap

**What happened:** Academia API created from scratch. Began with Docker-based setup, then migrated to SQLite for simplicity during development. GitHub repository initialized and first commit pushed.

| Date | Repo | Commit |
|------|------|--------|
| 2026-04-15 | academia-api | **Add gitignore** — Excluded secrets, venv, and build artifacts from version control |
| 2026-04-15 | academia-api | **Initial commit — Academia API** — Django REST API scaffolded with core models (alumnos, grupos, pagos, pagadores) |

**Decisions made:**
- Docker abandoned in favour of local SQLite during dev; Railway handles prod DB
- Core models scoped to: `Alumno`, `Grupo`, `Pago`, `Pagador`

---

## April 26, 2026 — Passive Income Brainstorm

> Working session focused on business strategy and product ideation, not code commits.

### Milestone: Product Concept — Cambridge PDF Resource

**Ideas explored:** Passive income streams compatible with the academia workload.

**Key outcome:** Identified the Cambridge PDF product as a viable side revenue stream — create and sell structured PDF worksheets/resources aligned to Cambridge English exam levels (A2, B1, B2, C1). Minimal ongoing work once created; distributable via Gumroad or similar.

**Why it fits:** Candela already produces teaching materials weekly; packaging them as a digital product has near-zero marginal cost.

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

## Week of May 25–29, 2026 — Full-Stack Launch

### Milestone: Full-Stack Launch + PDF Invoicing + Railway/Vercel Deployment

| Date | Repo | Commit |
|------|------|--------|
| 2026-05-27 | academia-api | **Add CRM/empresas/placement_test modules, invoice numbering, and module fixes** |
| 2026-05-27 | academia-api | **Add Railway deployment config and production settings** |
| 2026-05-27 | academia-frontend | **Initial commit — React+Vite frontend for academia management system** |
| 2026-05-27 | academia-frontend | **Guard s.registros against null in AsistenciaPage history render** |
| 2026-05-27 | academia-frontend | **Rebuild PagosPage with inline create form and full payment list** |
| 2026-05-27 | academia-frontend | **Rebuild AlumnosPage with improved cards, modal UX, and delete confirmation** |
| 2026-05-27 | academia-frontend | **Rebuild GruposPage with color accents, schedule chips, and delete modal** |
| 2026-05-27 | academia-frontend | **Rebuild PagadoresPage with proper delete modal and polished UX** |
| 2026-05-27 | academia-frontend | **Rebuild DashboardPage with KPI cards, pending payments, and birthdays** |
| 2026-05-27 | academia-frontend | **Rebuild CRMPage with edit, delete, interaction logging, and search** |
| 2026-05-27 | academia-frontend | **Rebuild remaining pages: Cumpleanos, Documentos, Pendientes, Config, Empresas** |
| 2026-05-27 | academia-frontend | **Add WhatsApp button to student cards linking to pagador's phone** |
| 2026-05-27 | academia-frontend | **Add vercel.json for SPA routing** |
| 2026-05-28 | academia-api | **Fix .env: remove corrupted settings.py content and PostgreSQL DATABASE_URL** |
| 2026-05-28 | academia-api | **Replace docx/local-disk invoices with ReportLab PDF + Google Drive** |
| 2026-05-28 | academia-api | **Auto-create 'Rangers Academy Facturas' Drive folder; add credentials to gitignore** |
| 2026-05-28 | academia-api | **Add Google Drive invoice storage with ReportLab PDF generation** |
| 2026-05-28 | academia-api | **Increase logo size and improve PDF layout spacing** |
| 2026-05-28 | academia-api | **Support GOOGLE_TOKEN_JSON env var for Railway deployment** |
| 2026-05-28 | academia-frontend | **Show error feedback on Cobrar button failure in PendientesPage** |
| 2026-05-29 | academia-api | **Add render.yaml with correct start and build commands** |

---

## Week of June 1–7, 2026 — Production Stabilization

### Milestone: Production Stabilization + Games + Email/WhatsApp Contact

| Date | Repo | Commit |
|------|------|--------|
| 2026-06-02 | academia-api | **Fix CORS, CSRF trusted origins, and Django 6.0 STORAGES config for Railway** |
| 2026-06-02 | academia-frontend | **Fix VITE_API_URL usage in refresh token interceptor** |
| 2026-06-03 | academia-api | **Fix invoice numbering system — sync Pago.num_doc with generated PDFs** |
| 2026-06-03 | academia-api | **Add email and WhatsApp contact endpoints for alumnos and pagadores** |
| 2026-06-03 | academia-frontend | **Add Flashcard and Memory Match games** |
| 2026-06-03 | academia-frontend | **Add email buttons, Word Scramble game, fix dashboard** |
| 2026-06-04 | academia-api | **Backfill invoices for Pagos 22 and 23** |
| 2026-06-04 | academia-api | **Auto-generate invoice PDF on payment creation** |
| 2026-06-04 | academia-api | **Test and clean up auto-invoice smoke test (pagos 25-26)** |
| 2026-06-04 | academia-api | **Update password for Academia2024 user** |
| 2026-06-04 | academia-frontend | **Pin Node >=20 for Vite 8 compatibility on Vercel** |

---

## June 10, 2026 — Deployment Day

> Major operational milestone. No new feature commits — this was the day everything was confirmed live and the dev environment was upgraded.

### Milestone: System Confirmed Live + Tooling Upgrade

**What happened:**

- **Railway + Vercel confirmed live** — both backend (Railway) and frontend (Vercel) verified working end-to-end in production
- **Claude Code CLI installed** — AI-assisted development workflow set up; Claude Code running locally for this project
- **Custom domain purchased** — domain acquired and pointed at the Vercel frontend

**Significance:** First day the full stack was live for real use, not just deployable. The domain purchase marks the transition from "internal tool" to "product."

---

## June 11, 2026 — Payment Dashboard + Invoice Logic

### Milestone: Payment Email Notifications + Dashboard Prototype

| Date | Repo | Commit |
|------|------|--------|
| 2026-06-11 | academia-api | **Fix recibo prefix (REC→RE), add email notification on payment creation** — Receipt serial corrected from `REC-` to `RE-`; payer now receives an email confirmation with the invoice PDF link when a payment is recorded |

**Additional work this session (pre-commit / prototype):**

- Payment dashboard prototype built — visual summary of monthly income, pending cobros, and overdue payments
- WhatsApp button logic reviewed and refined — confirmed correct phone number formatting (`34XXXXXXXXX`) for Spanish numbers
- Invoice generation logic audited end-to-end following the June 10 go-live; edge cases identified and queued for next session

---

## June 15, 2026 — Tech Briefing + Strategy + Tooling

> No code commits. Full working session focused on strategy, communication tooling, and file organisation.

### Milestone: Social Media Strategy + WhatsApp Business Setup + Internal Tooling

**Session breakdown:**

**Tech briefing:**
- Reviewed the full current system stack with a collaborator/student — walked through Django API, React frontend, Railway/Vercel deployment, and Google Drive invoice storage

**Social media strategy:**
- Drafted a content plan for Rangers Academia's social media presence
- Identified target platforms and posting cadence for student acquisition

**WhatsApp Business:**
- Created WhatsApp message templates for payment reminders, invoice delivery, and class confirmations
- Hit a glitch with WA Business account verification — account flagged during setup; workaround documented, escalation pending

**Internal tooling:**
- **File cleanup script** — script written to organise the local `academia/` project folder; removes temp files, archives old exports, normalises folder structure
- **Worksheet organiser** — tool to batch-rename and sort Cambridge worksheet PDFs by level (A2/B1/B2/C1) and topic; feeds into the Cambridge PDF product idea from April 26

---

## June 17, 2026 — Adult Programme + FUNDAE + Teaching Setup

> Session focused on a new revenue stream (adult corporate training) and teaching infrastructure.

### Milestone: Adult Programme Built + FUNDAE Calculator + Duet Display

**Adult programme:**
- Designed and built the structure for a new adult/corporate English programme within the academia system
- Separate grupo type and pricing tier for adult students vs. standard academy students

**FUNDAE calculator:**
- FUNDAE = Fundación Estatal para la Formación en el Empleo (Spanish state body that subsidises employee training)
- Built a calculator tool to determine how much of a company's training costs are recoverable via FUNDAE credits
- Relevant for B2B sales to empresas — lets Candela quote net cost after subsidy

**Duet Display + screen sharing:**
- Duet Display set up to use iPad as a second monitor
- Screen sharing workflow configured for online teaching — allows student to see the teacher's screen (whiteboard, exercises, materials) during Zoom/Teams sessions
- Replaces the need for a physical second screen in the teaching setup

---
