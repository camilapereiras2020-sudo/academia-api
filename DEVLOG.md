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
| 2026-06-21 | DEVLOG comprehensive rewrite (both repos) |
| 2026-06-30 | Multi-emisor invoicing (Cami&Co + Rangers Academy); modal positioning bug fixed app-wide; invoice failure surfacing |
| 2026-07-01 | Rangers Academy PDF theme; autónoma name/email on invoices; ensure_superuser deploy command |
| 2026-07-02 | Google Sheets bulk import tool for alumnos; dni field added; Railway release-phase Procfile bug fixed |
| 2026-07-03 | CRM adult/self-pay support (`es_adulto`) end-to-end: form fields, Contactos sheet export, auto-fill pagador, Matricular button, conditional validation |
| 2026-07-03 | GruposPage search box; PagosPage manual invoice/receipt generation button |
| 2026-07-03 | Class page core: `/grupos/:id` route with lesson log, homework tracker, struggle tracker |
| 2026-07-04 | Tarifa pricing system (Rangers Academy rates + Cami&Co manual entry), wired into Nuevo Pago with a horas-worked field |
| 2026-07-04 | marca (brand) field added to Alumno/Pago/Lead, with brand filter toggles on Alumnos and Pagos |
| 2026-07-04 | Modal positioning re-fixed (portal-based) in Alumnos/Pagadores; Railway auto-deploy webhook trigger repaired |

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

## June 21, 2026 — DEVLOG Rewrite

| Date | Repo | Commit |
|------|------|--------|
| 2026-06-21 | academia-api | **DEVLOG: comprehensive rewrite with milestones table and missing sessions** |
| 2026-06-21 | academia-frontend | **Add DEVLOG.md — full frontend development log with milestones table** |

**What happened:** Both repos' development logs backfilled in full for the first time, covering everything from the April 14–15 bootstrap through June 11. Milestones tables added to the top of each file for fast scanning.

---

## June 30, 2026 — Multi-Emisor Invoicing + App-Wide Modal Bug Fix

### Milestone: Rangers Academy Becomes a Second Invoicing Entity + Critical UI Bug Fixed

**System context:** Up to this point, all invoices were generated under a single hardcoded issuer ("Cami&Co"). Rangers Academia needed to invoice under its own name/NIF as a second entity issuing from the same system.

| Date | Repo | Commit |
|------|------|--------|
| 2026-06-30 | academia-api | **Multi-emisor invoices, Drive upload, grupos_detalle fix, modal repairs** |
| 2026-06-30 | academia-api | **Hotfix: seed_emisores in release phase; fix_legacy_docs handles Drive 404s** |
| 2026-06-30 | academia-api | **Surface invoice generation failures in pago notas field** |
| 2026-06-30 | academia-api | **fix: seed Drive folder IDs correctly; regenerate missing invoices on deploy** |
| 2026-06-30 | academia-frontend | **Fix modal positioning and Descargar button behaviour** |
| 2026-06-30 | academia-frontend | **feat(documentos): show creation datetime on every document row** |

**New `Emisor` model (multi-tenant invoicing):**
- Stores per-issuer company info: `nombre`, NIF, IBAN, Drive folder ID, invoice-number prefix/baseline
- `Pago` gains a FK to `Emisor` so every payment records which entity issued it
- `invoice_service.generate_invoice_for_pago` now reads all fields from the linked `Emisor` instead of hardcoded "Cami&Co" strings; `_next_invoice_number` is keyed per-emisor prefix
- `seed_emisores` management command upserts both Cami&Co and Rangers Academy `Emisor` records with real NIF/IBAN/Drive folder IDs, run on every deploy via the Procfile release phase

**Bugs fixed this session:**

| Bug | Root cause | Fix |
|-----|-----------|-----|
| `seed_emisores` wiped correct Drive folder IDs on every deploy | `update_or_create(defaults={"drive_folder_id": ""})` overwrote the real ID with an empty string each run, forcing fallback to a deleted env var → every invoice upload 404'd | Switched to `get_or_create` + conditional update that never overwrites an already-set `drive_folder_id` |
| Invoice generation failures were silently swallowed | No surface for errors (Drive folder deleted, quota exceeded, etc.) | Failures now written into `pago.notas` so they're visible in the Pagos list UI, plus logged to stdout |
| Legacy documents pointing at deleted/missing Drive files | Pre-migration `Documento` records had `s3_key` set but the actual Drive file was gone | `fix_legacy_docs` management command re-generates PDFs from the linked `Pago`, re-uploads to Drive, and repairs `s3_key`; falls back to the Cami&Co emisor for pre-migration records with `pago.emisor = NULL`; accepts `--check-s3` to audit all keys against Drive |
| Missing invoices for older pagos | Some existing payments never had a `Documento` generated | New `fix_missing_invoices` management command (runs in release phase) auto-generates invoices for any pago with no linked documento |
| **All 11 modal overlays across the app rendered off-position** (Alumnos, Grupos, Pagadores, Pagos, CRM, Empresas, Documentos) | The `fadeUp` CSS animation ended on `transform: translateY(0)` instead of `transform: none` — a zero-translate still creates a new stacking context, which breaks `position: fixed` centering | Changed animation end-state to `transform: none` in `index.css` — fixed every modal in the app with a one-line change |
| "Descargar" on documents silently downloaded instead of opening the PDF; broken in production | `<a>` had `download` attribute and used a hardcoded `/api/v1` path (only worked on localhost) | Removed `download`, added `target="_blank"`, switched to `VITE_API_URL` so it resolves correctly on Vercel → Railway |

**Also shipped:**
- `AlumnoSerializer` gained `grupos_detalle` (wraps the single grupo FK in the array shape the frontend already expected) and an `fnac` alias for `fecha_nacimiento`; `asignar-grupo` action and a search filter added to `AlumnoViewSet`
- Document rows in `DocumentosPage` now show their creation datetime
- `ripple.py` health-checker updated to match renamed functions from this session's refactor

---

## July 1, 2026 — Rangers Academy Invoice Branding + Deploy Hardening

| Date | Repo | Commit |
|------|------|--------|
| 2026-07-01 | academia-api | **Add Rangers Academy PDF theme + ensure_superuser command** |
| 2026-07-01 | academia-api | **Show autonoma name + email in DE block; add Emisor.email field** |

**Rangers Academy invoice theme:**
- `invoice_service.py` gained a theme system (`THEME_CAMIANDCO` / `THEME_RANGERS`) — Rangers uses a forest green (`#314922`) accent, cream (`#F5EDD6`) background, and a square badge logo, plus its own inspirational quote; Cami&Co's theme is unchanged
- Rangers logo asset added, resized to 400×400 for PDF embedding

**Invoice content fixes:**
- `Emisor` gained an `email` field; `seed_emisores` updated with Rangers' real address (Rúa dos Ferreiros 26), phone, and `info@rangersacademy.es`
- Invoice "emisor" block now shows the autónoma's own name and email alongside the company info, and the label changed from **CIF to NIF** (autónomos use NIF, not CIF — the previous label was incorrect)

**Deploy hardening:**
- New `ensure_superuser` management command — idempotent superuser creation from env vars, added to the Procfile release phase ahead of `seed_emisores`

---

## July 2, 2026 — Alumnos Google Sheets Import Tool

### Milestone: Bulk Student Import via Google Sheets + Railway Release-Phase Bug Discovered

| Date | Repo | Commit |
|------|------|--------|
| 2026-07-02 | academia-api | **Add Google Sheets bulk import tool for alumnos** |
| 2026-07-02 | academia-api | **Add dni field to Alumno, add --row flag to import script** |
| 2026-07-02 | academia-api | **Fix Procfile: Railway doesn't run the Heroku-style release phase** |
| 2026-07-02 | academia-frontend | **CRM: only require nombre padre/madre and nombre alumno in nueva consulta** |

**Google Sheets import tool built:**
- `create_import_template.py` builds (or repairs in place) a Google Sheet template with ALUMNO / PAGADOR / GRUPO column groups, dropdown validation, and TEXT-formatted date/phone/IBAN columns
- `import_from_sheets.py` reads the sheet and creates alumnos via the platform API, matching or creating pagador/grupo records by name, and skipping alumnos that already exist; `--row` added to import a single row for testing without touching other in-progress rows
- `Alumno.telefono`, `.email`, and `.aviso_cumple_dias` restored (they had been removed in a prior migration in favor of Pagador-only contact info) — this also fixed `AlumnosPage.tsx`, which already had dead form inputs for these fields that the old serializer had been silently dropping
- `Alumno.dni` added after the sheet template gained a `dni_alumno` column during real data entry, wired through the import script and template

**Critical infrastructure bug found and fixed:**
- The Procfile's `release:` line had **never executed** — Railway's Nixpacks builder only runs the `web:` process from a Procfile, unlike Heroku, so every migration and management command listed under `release:` (including `ensure_superuser`, `seed_emisores`, `fix_legacy_docs`) had silently never run on any deploy
- Discovered because the new `alumnos.dni`/`telefono`/`email` migrations never applied in production despite the deploy reporting success — causing 500 errors on `/pagadores/`. `documentos.0004_emisor_email` was found stuck unapplied for the same reason
- Both migrations applied manually; going forward, release-phase commands are folded directly into the `web:` start command so they always run

**Frontend:** CRM's "nueva consulta" form loosened — only nombre padre/madre and nombre alumno remain required; teléfono, objetivo, origen, edad, curso, and email are now optional. Teléfono still validates as a Spanish mobile number (9 digits, starting 6/7/9) when filled in.

---

## July 3, 2026 — CRM Adult/Self-Pay Support, Matriculation Flow, Contactos Sheet Export

### Milestone: Adult Students Can Self-Enroll and Self-Pay End-to-End

**Context:** Rangers Academia serves both children (parent is the contact/payer) and adult students (who are their own contact and payer). The CRM previously assumed every lead had a separate parent/guardian contact — this session made "adult, self-paying" a first-class path from lead capture through enrollment.

| Date | Repo | Commit |
|------|------|--------|
| 2026-07-03 | academia-api | **Add double-click launcher for the alumnos import script** |
| 2026-07-03 | academia-api | **Auto-export new CRM leads to the Contactos Google Sheet tab** |
| 2026-07-03 | academia-api | **Hardcode project path in importar_alumnos.bat** |
| 2026-07-03 | academia-api | **Add es_adulto/pagador_es_alumno to Lead, autofill pagador on enrollment** |
| 2026-07-03 | academia-api | **CRM: guard convertir-alumno against double matriculation, return names** |
| 2026-07-03 | academia-api | **CRM: make nombre_contacto optional when es_adulto is true** |
| 2026-07-03 | academia-frontend | **Update CRM origen/objetivo options to match new taxonomy** |
| 2026-07-03 | academia-frontend | **CRM: add adult/self-pay checkbox and payer dropdown to nueva consulta form** |
| 2026-07-03 | academia-frontend | **CRM: add Matricular button to convert a lead into an Alumno/Pagador** |
| 2026-07-03 | academia-frontend | **CRM: make Nombre padre/madre optional when adulto is checked** |
| 2026-07-03 | academia-frontend | **GruposPage: add search by nombre or nivel** |
| 2026-07-03 | academia-frontend | **PagosPage: add manual generate invoice/receipt button for pagos without a doc** |

**Contactos Google Sheet export (new):**
- `Lead.origen`/`objetivo` choices simplified to a fixed taxonomy (`telefono`/`whatsapp`/`instagram`/`facebook`/`recomendacion`/`web` and `general`/`cambridge`/`ib`/`adultos`) to match the sheet's dropdown validation; existing leads keep their old raw values
- `add_contactos_sheet.py` creates/repairs a "Contactos" tab in the shared Google Sheet with columns: fecha, nombre_padre_madre, nombre_alumno, telefono, email, edad_alumno, curso_escolar, objetivo, origen, etapa_crm, notas, **es_adulto**
- `LeadViewSet.perform_create` now appends a row to that sheet on every new lead via `modules/crm/sheets_service.py`; failures are logged but never block lead creation
- Frontend origen/objetivo `<select>` options updated to match the new backend taxonomy exactly

**Adult / self-pay feature (`es_adulto`, `pagador_es_alumno`):**
- Two new boolean fields on `Lead`: `es_adulto` ("the student is an adult") and `pagador_es_alumno` ("the student pays for themselves")
- "Nueva consulta" form gained a checkbox — "El alumno es adulto / paga el mismo" — that reveals a dropdown ("El mismo alumno es el pagador" / "Otro pagador") when checked
- `nombre_contacto` (nombre padre/madre) is now **optional** whenever `es_adulto` is true — relabeled to "Nombre contacto (opcional)" on the frontend, and validated conditionally in `LeadSerializer.validate()` on the backend (model-level `blank=True` can't express a conditional-required rule on its own)
- When such a lead is enrolled, `convertir_alumno` now creates the `Pagador` using the **alumno's own name** (instead of the contact's) whenever `es_adulto and pagador_es_alumno` are both true

**Matriculation flow built (previously missing entirely):**
- Before this session, moving a CRM lead to the "Matriculado" stage only changed its pipeline label — no `Alumno`/`Pagador` was ever actually created. A real **"Matricular"** button now appears on lead cards and the detail panel once a lead reaches that stage
- Clicking it opens a form to pick grupo (auto-filling the monthly fee from the group's `tarifa`), mensualidad, and fecha de inicio, then calls `convertir-alumno`
- `convertir_alumno` gained a guard against double-matriculation (returns an error if the lead already has a linked alumno, preventing duplicate `Alumno` records) and now returns `alumno_nombre`/`pagador_nombre`/`pagador_autocompletado` so the frontend can show a confirmation without extra requests
- Confirmation modal shows the created alumno + pagador names, a note ("Pagador creado automáticamente con los datos del alumno") when the payer was auto-filled, and a **"Ver perfil del alumno"** link
- Since `AlumnosPage` has no per-student detail route, that link navigates to `/alumnos?openId=<id>`; `AlumnosPage` now reads that query param and auto-opens the matching alumno's edit modal on load

**Also shipped:**
- Double-click launcher (`.bat`) for the alumnos Sheets import script, with its project path hardcoded after a copy on the Desktop broke the original `%~dp0`-relative version
- `GruposPage` gained a search box filtering by nombre or nivel, matching the search pattern already used on Alumnos/CRM
- `PagosPage`: any pago missing `num_doc` now shows a 🧾 button that calls `documentosApi.generar` (tipo inferred from `metodo` — transferencia/tarjeta → factura, otherwise recibo), giving a manual fallback for payments that never got an invoice/receipt generated

---

## July 3–4, 2026 — Class Pages, Pricing/Tariff System, Brand Field, Deploy Pipeline Fix

### Milestone: Class Hub, Real Pricing Rates, Multi-Brand Data Model

**Context:** ROADMAP.md was added to track four longer-horizon feature ideas (smart calendar, class hub, WhatsApp/email homework delivery, auto parent messaging). This session built out the second item — a per-group class page — then moved on to giving payments a real pricing model instead of free-typed amounts, and finally tagging students/payments/leads by which of the two brands (Cami&Co vs Rangers Academy) they belong to.

| Date | Repo | Commit |
|------|------|--------|
| 2026-07-03 | academia-api | **Add ROADMAP.md with four feature ideas: smart calendar, class hub, WhatsApp/email homework delivery, auto parent messaging** |
| 2026-07-03 | academia-api | **Add class page core: lesson log content, homework tracker, struggle tracker** |
| 2026-07-03 | academia-api | **Fix Tarea creation: wrap completados bulk-create in a transaction** |
| 2026-07-03 | academia-frontend | **Add class page: new /grupos/:id route with lesson log, homework, struggle tracker** |
| 2026-07-03 | academia-frontend | **GrupoDetailPage: require fecha_asignada before saving a tarea** |
| 2026-07-04 | academia-api | **ROADMAP: note materials-upload implementation details, still deferred** |
| 2026-07-04 | academia-frontend | **Fix modal positioning in AlumnosPage and PagadoresPage via portal** |
| 2026-07-04 | academia-api | **Add Tarifa pricing model and link it to Pago** |
| 2026-07-04 | academia-frontend | **Add tarifa selector to Nuevo Pago, auto-filling the amount** |
| 2026-07-04 | academia-api | **Make Pago.grupo optional** |
| 2026-07-04 | academia-frontend | **Make grupo optional and decouple tarifa from grupo in Nuevo Pago** |
| 2026-07-04 | academia-frontend | **Add horas field and harden the tarifa dropdown in Nuevo Pago** |
| 2026-07-04 | academia-api | **import_from_sheets.py: update existing alumnos instead of skipping** |
| 2026-07-04 | academia-api | **Add marca (brand) field to Alumno, Pago, and Lead** |
| 2026-07-04 | academia-frontend | **Add brand (marca) filter toggle to AlumnosPage and PagosPage** |

**Class pages (`/grupos/:id`):**
- First per-record route in the app — every other page is list+modal. New `modules.clases` app adds `Tarea`/`TareaCompletada` (homework, mirroring `Sesion`/`RegistroAsistencia`) and `NotaDificultad` (per-student struggle/topic notes, mirroring `crm.Interaccion`)
- `Sesion` gained a `contenido` field (lesson-log content), separate from the existing `notas`
- Frontend `GrupoDetailPage` presents lesson log, homework tracker, and struggle tracker for a single group; a bug where `Tarea` could be saved without `fecha_asignada` was fixed, and the backend's `completados` bulk-create was wrapped in a transaction so a partial failure can't leave a `Tarea` half-populated

**Tarifa pricing system (new `modules.tarifas` app):**
- `Tarifa` model: `nombre` (Clase Grupo / Bono Familia / Clase Privada / Clase Recuperada), `tipo_cobro` (por_hora / mensual / bono_familiar), `marca`, `precio`, optional `horas_semanales` (1–3)
- Seeded with Rangers Academy's real rate card (Clase Grupo: €12/h or €48–135/mes for 1–3h/semana; Bono Familia: €90–260/mes for 1–3h/semana) plus Clase Privada/Recuperada and all of Cami&Co's categories as manual-entry placeholders (no fixed price)
- `Pago` gained an optional `tarifa` FK. Nuevo Pago's tarifa dropdown (grouped by brand) auto-fills and **locks** the amount for Rangers' fixed-price combos, and leaves it freely editable for Cami&Co and for Clase Privada/Recuperada
- `grupo` on `Pago` was made optional and fully decoupled from pricing — selecting a grupo no longer overwrites the amount; only the tarifa selector does, so a payment's tariff no longer has to match whichever group the student happens to be in
- New optional **Horas** field (decimal, e.g. `1.5`) on Nuevo Pago, mapped to the pre-existing `Pago.horas_trabajadas` field that had never been exposed in this form
- Verified live with a real browser (Playwright) rather than by inspection alone: confirmed all seeded tarifa options render, group correctly by brand, and that selecting a fixed-price tarifa locks the amount while Clase Privada/manual ones don't; hardened the dropdown to skip rendering a brand's optgroup with zero options and to show a loading placeholder while the tarifas request is in flight

**marca (brand) field:**
- `Alumno`, `Pago`, and `Lead` each gained a `marca` field (`cami_and_co` / `rangers_academy`, default `rangers_academy`), reusing the choices already defined on `Tarifa`
- `AlumnoViewSet` and `PagoViewSet` accept a `?marca=` filter; `AlumnosPage` and `PagosPage` got a Rangers Academy / Cami & Co / Todas toggle wired to it

**Bugs fixed this session:**

| Bug | Root cause | Fix |
|-----|-----------|-----|
| Modal positioning regressed again in AlumnosPage/PagadoresPage — dialogs rendered far down the page instead of centered | The June 30 `fadeUp`-animation fix addressed one cause, but these two pages' modals were still nested under `AppShell`'s animated wrapper, which could re-establish itself as the containing block for `position: fixed` | Rendered both pages' modals through a React portal to `document.body`, which is immune to any ancestor's transform/animation state, not just the one already fixed |
| GitHub pushes to `academia-api` stopped auto-deploying on Railway sometime after 2026-07-03 — two real feature pushes today landed with no new deployment | Railway's `DeploymentTrigger` record for the `academia-api` service had been deleted entirely (confirmed via the Railway GraphQL API: `repoTriggers` returned an empty list, while `academia-frontend`'s equivalent trigger was intact) | Recreated the trigger via `deploymentTriggerCreate` (branch `main`, provider `github`, same repository/environment/service as before); verified fixed by watching a real push immediately start a new Railway deployment |

**Also shipped:**
- `import_from_sheets.py` no longer skips alumnos that already exist in the sheet — it now patches `telefono`, `email`, `nivel`, `pagador`, and `grupo` when the sheet's value differs from the current one, matching by nombre+apellido. A blank sheet cell is never treated as "clear this field."

---
