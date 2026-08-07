# ROADMAP — Rangers Academia

Feature ideas captured for future work. Not scheduled — this is a backlog, not a commitment.

---

## 1. Smart Calendar with Class Pages

**What:** A visual calendar showing class blocks color-coded by teacher (Cami / Cande). Each block is clickable and opens that class's dedicated page.

**Details:**
- Max 5–6 students per class (hard cap enforced when assigning students to a group)
- Auto-suggest compatible classes for a new student based on: level, age, and available spots (i.e. classes under the 5–6 cap)
- Color coding by teacher makes it easy to see each teacher's weekly load at a glance

**Why:** Currently grupos/horarios exist as data but there's no visual, click-through calendar view — this would turn the schedule into a real planning tool instead of a list.

---

## 2. Class Page as Teaching Hub

**What:** Each class (grupo) gets its own page that acts as the actual workspace for running that class, not just a roster.

**Details:**
- Drag-and-drop file upload (materials, worksheets, recordings)
- Syllabus tracker for the group
- Lesson log — what was covered each session
- Homework tracker — what was assigned, due dates, completion status
- Per-student "struggle tracker" — flag topics/skills a specific student is having trouble with, visible over time

**Status (2026-07-04):** Lesson log, homework tracker, and struggle tracker are built (`/grupos/:id` page, `modules/clases` app). Materials upload is still deferred — implementation notes below for whenever it's picked up.

**Materials upload — implementation notes (researched, not built):**
- The existing Drive integration (`modules/documentos/invoice_service.py`) is **OAuth2 user-delegated credentials**, not a service account — sourced from `GOOGLE_TOKEN_JSON` env var (prod) or `.google-token.json` (local), refresh-token based, scope `https://www.googleapis.com/auth/drive`. Any reuse needs to account for this (token expiry/revocation tied to whichever human account authorized it, quota is that user's personal Drive quota).
- `upload_to_drive()`/`download_from_drive()` in that file are invoice-specific — hardcoded `application/pdf` mimetype and a fixed `Facturas {year}/T{n}` folder path baked in. Materials need new/generalized upload+download functions (arbitrary mimetype, arbitrary folder path), reusing only the lower-level `_credentials()`/`_drive()`/`_folder()` helpers.
- The Rangers root Drive folder is `Emisor.objects.get(slug="rangers").drive_folder_id` (id `17xDVHjzwsvaRIVhSiNAVLlFeNF-d7tF-`) — code comments call it "Rangers-Invoice", not literally "Rangers Academy Facturas" (that string only appears in a DEVLOG changelog blurb). A `Materiales/{grupo_nombre}` subfolder would nest under this same root via two `_folder()` calls.
- `Documento` (the existing invoice/receipt model) has **no FK to `Grupo`** and its fields (`tipo` choices `factura/recibo/otro`, `pago` FK, `num_doc`) are invoice-shaped — reusing it as-is doesn't cleanly support "material tied to a grupo." Needs either a new `Material` model (grupo FK, nombre, drive_file_id, mime_type, uploaded_at) or a `grupo` FK + new `tipo` choice added to `Documento`. Leaning toward a new model to keep invoicing and class materials decoupled — decide before building.
- No drag-and-drop library or `<input type="file">`/FormData pattern exists anywhere in the frontend yet — this is a from-scratch build on both ends, not a refactor of an existing pattern.

**Why:** Consolidates what's probably currently tracked in notes/memory/paper into one place tied to the actual class record.

---

## 3. Homework Delivery via WhatsApp/Email (No Login Required)

**What:** Homework gets pushed directly to students via WhatsApp or email — it goes *to* them, rather than requiring them to log into a portal to check it.

**Why:** Removes the login-friction that kills adoption for a homework portal, especially for younger students or less tech-savvy parents. Fits the existing WhatsApp/email contact infrastructure already built for pagadores/alumnos.

---

## 4. Automatic Parent Message After Each Class

**What:** After each class, an automatic message is sent to the parent covering:
- What was covered in that session
- Homework that was set
- Exam alerts (if relevant/upcoming)
- Available extra class spots (upsell opportunity)

**Template tone:** Warm, professional, signed by the teacher's name (not a generic "Rangers Academia" signature).

**Why:** Keeps parents in the loop automatically without manual per-student follow-up, and doubles as a natural upsell channel for extra classes.

---

## 5. Visual Group Scheduling — Backend Constraint Data (not started, needs design)

**What:** Backend half of the drag-and-drop Timetable Builder feature — full feature spec lives in `academia-frontend/ROADMAP.md` ("Visual Group Scheduling / Timetable Builder"), noted here because the scheduling-constraint data model and conflict-check logic would live in this repo.

**Backend-relevant pieces:**
- Structured per-student availability constraints (e.g. "only available Tuesdays/Thursdays 19:00-21:00") stored on the student model — not decided yet where/how granular (new model vs. fields on `Alumno`, days-of-week + time-range representation, one-off exceptions vs. recurring only)
- Slot-conflict validation: given a student + a target group/timeslot, check stored constraints and return a warning/block signal for the frontend to surface before assignment is confirmed
- Depends on Group CRUD existing in the platform UI first (see frontend roadmap) and likely also needs `Grupo.horarios` (currently an undocumented/always-empty JSONField, see `modules/grupos/models.py`) to gain a real, query-able schedule shape before conflict-checking is possible at all

**Priority:** real feature, needs its own design pass — not a quick build. Noted here so it isn't lost, not scheduled yet.

---

## Notes

These four ideas overlap: #2 (class page/lesson log) is the natural data source for #3 (homework delivery) and #4 (parent auto-message) — building the class page first would make the other two mostly a matter of wiring up delivery channels to data that already exists.
