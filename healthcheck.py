"""
Production health check for the invoicing system.
Run with: railway run python healthcheck.py
"""
import os, sys, json, io
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from modules.documentos.models import Documento, Emisor
from modules.pagos.models import Pago
from modules.documentos.invoice_service import (
    _drive, generate_invoice_for_pago, upload_to_drive, generate_pdf_bytes
)

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"
results = []

def log(status, section, msg):
    tag = f"[{status}]"
    print(f"{tag:8} {section}: {msg}")
    results.append((status, section, msg))


# ── 1. GOOGLE CREDENTIALS ────────────────────────────────────────────────────
print("\n=== 1. GOOGLE CREDENTIALS ===")
raw = os.environ.get("GOOGLE_TOKEN_JSON", "")
sa_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")

if not raw:
    log(WARN if sa_raw else FAIL, "Token", "GOOGLE_TOKEN_JSON env var is empty (this is the primary credential — needed for uploads)")
else:
    try:
        td = json.loads(raw)
        scopes = td.get("scopes", [])
        has_refresh = bool(td.get("refresh_token"))
        log(PASS, "Token", f"JSON valid | scopes={scopes} | has_refresh_token={has_refresh}")
        if "https://www.googleapis.com/auth/drive.file" in scopes and \
           "https://www.googleapis.com/auth/drive" not in scopes:
            log(WARN, "Token", "Scope is drive.file (restricted) — upgrade to drive scope recommended")
    except Exception as e:
        log(FAIL, "Token", f"JSON parse error: {e}")

if sa_raw:
    log(WARN, "ServiceAccount", "GOOGLE_SERVICE_ACCOUNT_JSON is set — used only as a fallback if no OAuth2 token is present. It can read Drive but CANNOT upload (no storage quota on a personal Gmail Drive).")


# ── 2. DRIVE AUTH ────────────────────────────────────────────────────────────
print("\n=== 2. DRIVE AUTH ===")
try:
    service = _drive()
    about = service.about().get(fields="user").execute()
    user = about.get("user", {})
    log(PASS, "Drive auth", f"Authenticated as {user.get('emailAddress')}")
except Exception as e:
    log(FAIL, "Drive auth", f"Cannot connect to Drive: {e}")
    service = None


# ── 3. DRIVE FOLDER ACCESS ───────────────────────────────────────────────────
print("\n=== 3. DRIVE FOLDER ACCESS ===")
folders = {
    "Cami&Co":          "1W3Jt5XMelFeUa_W4Gr8r381R4Gaz1imn",
    "Rangers Academy":  "17xDVHjzwsvaRIVhSiNAVLlFeNF-d7tF-",
}
if service:
    for name, fid in folders.items():
        try:
            f = service.files().get(fileId=fid, fields="id,name").execute()
            log(PASS, f"Folder:{name}", f"Accessible -> '{f['name']}'")
        except Exception as e:
            log(FAIL, f"Folder:{name}", f"Not accessible: {e}")
else:
    log(FAIL, "Folders", "Skipped — Drive auth failed")


# ── 4. EMISOR RECORDS ────────────────────────────────────────────────────────
print("\n=== 4. EMISOR RECORDS ===")
for slug in ("camiandco", "rangers"):
    try:
        e = Emisor.objects.get(slug=slug)
        issues = []
        if not e.nif:       issues.append("missing nif")
        if not e.drive_folder_id: issues.append("missing drive_folder_id")
        if not e.iban and slug == "camiandco": issues.append("missing iban")
        if issues:
            log(WARN, f"Emisor:{slug}", f"{e.nombre} — {', '.join(issues)}")
        else:
            log(PASS, f"Emisor:{slug}", (
                f"{e.nombre} | NIF={e.nif} | "
                f"factura_prefix={e.factura_prefix} baseline={e.factura_baseline} | "
                f"recibo_prefix={e.recibo_prefix} baseline={e.recibo_baseline} | "
                f"drive={e.drive_folder_id} | activo={e.activo}"
            ))
    except Emisor.DoesNotExist:
        log(FAIL, f"Emisor:{slug}", "Record not found — run seed_emisores")


# ── 5. PAGO RECORDS ──────────────────────────────────────────────────────────
print("\n=== 5. PAGO RECORDS ===")
pagos = list(Pago.objects.select_related("emisor", "alumno", "pagador").order_by("id"))
log(PASS if pagos else WARN, "Pagos", f"{len(pagos)} pago(s) in DB")

orphan_pagos = []
no_numdoc    = []
no_emisor    = []

for p in pagos:
    has_doc    = p.documentos.exists()
    has_numdoc = bool(p.num_doc)
    has_emisor = p.emisor is not None
    if not has_doc:    orphan_pagos.append(p)
    if not has_numdoc: no_numdoc.append(p)
    if not has_emisor: no_emisor.append(p)
    print(f"  Pago {p.id:>3} | {p.num_doc or '(no num_doc)':>15} | "
          f"emisor={p.emisor.nombre if p.emisor else 'NONE':>18} | "
          f"doc={'YES' if has_doc else 'NO':>3} | "
          f"{p.alumno.nombre if p.alumno else f'(sin completar: {p.estado_carga})'}")

if orphan_pagos:
    log(WARN, "Pagos", f"{len(orphan_pagos)} pago(s) have no linked Documento")
if no_numdoc:
    log(WARN, "Pagos", f"{len(no_numdoc)} pago(s) have no num_doc")
if no_emisor:
    log(WARN, "Pagos", f"{len(no_emisor)} pago(s) have no emisor")


# ── 6. DOCUMENTO RECORDS + DRIVE VERIFY ──────────────────────────────────────
print("\n=== 6. DOCUMENTO RECORDS ===")
docs = list(Documento.objects.select_related("pago").order_by("id"))
log(PASS if docs else WARN, "Documentos", f"{len(docs)} documento(s) in DB")

broken_docs  = []
missing_s3   = []

for d in docs:
    if not d.s3_key:
        missing_s3.append(d)
        log(WARN, f"Doc:{d.id}", f"{d.nombre} — no s3_key (cannot download from Drive)")
        continue

    if not service:
        log(WARN, f"Doc:{d.id}", f"{d.nombre} — Drive auth failed, skipping verify")
        continue

    try:
        service.files().get(fileId=d.s3_key, fields="id,name,size").execute()
        log(PASS, f"Doc:{d.id}", f"{d.nombre} — Drive file exists")
    except Exception as e:
        broken_docs.append(d)
        log(FAIL, f"Doc:{d.id}", f"{d.nombre} — Drive 404/error: {e}")


# ── 7. FIX BROKEN DOCUMENTS ──────────────────────────────────────────────────
if broken_docs or orphan_pagos:
    print("\n=== 7. FIXING BROKEN DOCUMENTS ===")

    # Fix: docs with broken/missing Drive files — try to re-upload
    for d in broken_docs:
        if not d.pago:
            log(FAIL, f"Fix:{d.id}", f"{d.nombre} — no linked pago, cannot regenerate")
            continue
        pago = Pago.objects.select_related(
            "emisor", "pagador", "alumno", "grupo"
        ).get(id=d.pago_id)
        if not pago.emisor:
            log(FAIL, f"Fix:{d.id}", f"{d.nombre} — pago has no emisor, cannot regenerate")
            continue
        try:
            num_doc, drive_id = generate_invoice_for_pago(pago, d.tipo)
            d.s3_key   = drive_id
            d.num_doc  = num_doc
            d.nombre   = f"{num_doc}.pdf"
            d.save(update_fields=["s3_key", "num_doc", "nombre"])
            pago.num_doc = num_doc
            pago.save(update_fields=["num_doc"])
            log(PASS, f"Fix:{d.id}", f"Regenerated → {num_doc} (drive={drive_id})")
        except Exception as e:
            log(FAIL, f"Fix:{d.id}", f"Regeneration failed: {e}")

    # Fix: pagos with no documento but with emisor — generate one
    for p in orphan_pagos:
        if not p.emisor:
            log(WARN, f"Fix:Pago{p.id}", "No emisor — assigning Cami&Co default")
            try:
                camiandco = Emisor.objects.get(slug="camiandco")
                p.emisor = camiandco
                p.save(update_fields=["emisor"])
            except Emisor.DoesNotExist:
                log(FAIL, f"Fix:Pago{p.id}", "Cami&Co emisor not found")
                continue

        # Re-fetch with full select_related
        p = Pago.objects.select_related("emisor", "pagador", "alumno", "grupo").get(id=p.id)
        try:
            from modules.pagos.constants import METODOS_FACTURA
            tipo = "factura" if (p.metodo or "").lower() in METODOS_FACTURA else "recibo"
            num_doc, drive_id = generate_invoice_for_pago(p, tipo)
            from datetime import date
            Documento.objects.update_or_create(
                pago=p,
                defaults=dict(
                    academia   = p.academia,
                    tipo       = tipo,
                    nombre     = f"{num_doc}.pdf",
                    num_doc    = num_doc,
                    s3_key     = drive_id,
                    local_path = "",
                    mime_type  = "application/pdf",
                ),
            )
            p.num_doc = num_doc
            p.save(update_fields=["num_doc"])
            log(PASS, f"Fix:Pago{p.id}", f"Document generated → {num_doc}")
        except Exception as e:
            log(FAIL, f"Fix:Pago{p.id}", f"Failed: {e}")
else:
    print("\n=== 7. NO FIXES NEEDED ===")


# ── 8. END-TO-END INVOICE TEST ───────────────────────────────────────────────
print("\n=== 8. END-TO-END INVOICE TEST ===")

def run_e2e_test(emisor_slug, label):
    from modules.alumnos.models import Alumno
    from modules.pagadores.models import Pagador
    from modules.grupos.models import Grupo
    from django.contrib.auth import get_user_model
    from datetime import date

    User = get_user_model()

    emisor = Emisor.objects.filter(slug=emisor_slug).first()
    if not emisor:
        log(FAIL, f"E2E:{label}", f"Emisor '{emisor_slug}' not found")
        return

    academia = emisor.academia

    # Find or create a test pagador
    pagador, _ = Pagador.objects.get_or_create(
        academia=academia,
        nombre="TEST Pagador Healthcheck",
        defaults=dict(nif="00000000T", email="test@healthcheck.local", telefono="600000000"),
    )

    # Find or create a test alumno
    alumno, _ = Alumno.objects.get_or_create(
        academia=academia,
        nombre="TEST Alumno Healthcheck",
        defaults=dict(pagador=pagador),
    )

    # Find or create a test grupo
    grupo, _ = Grupo.objects.get_or_create(
        academia=academia,
        nombre="TEST Grupo Healthcheck",
        defaults=dict(nivel="test", tarifa="10.00"),
    )

    # Create a test pago
    pago = Pago.objects.create(
        academia    = academia,
        alumno      = alumno,
        pagador     = pagador,
        grupo       = grupo,
        emisor      = emisor,
        mensualidad = "10.00",
        descuento   = "0.00",
        total       = "10.00",
        metodo      = "transferencia",
        periodo     = date.today().strftime("%Y-%m"),
        fecha       = date.today(),
        notas       = "Healthcheck test",
        estado      = "pagado",
    )
    log(PASS, f"E2E:{label}", f"Pago created (id={pago.id})")

    # Generate invoice
    try:
        num_doc, drive_id = generate_invoice_for_pago(pago, "factura")
        Documento.objects.create(
            academia   = academia,
            pago       = pago,
            tipo       = "factura",
            nombre     = f"{num_doc}.pdf",
            num_doc    = num_doc,
            s3_key     = drive_id,
            local_path = "",
            mime_type  = "application/pdf",
        )
        pago.num_doc = num_doc
        pago.save(update_fields=["num_doc"])
        log(PASS, f"E2E:{label}", f"Invoice generated: {num_doc} -> Drive {drive_id}")
    except Exception as e:
        log(FAIL, f"E2E:{label}", f"Invoice generation failed: {e}")
        pago.delete()
        return

    # Download and verify
    try:
        from googleapiclient.http import MediaIoBaseDownload
        request    = service.files().get_media(fileId=drive_id)
        buf        = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        pdf_bytes = buf.getvalue()
        is_pdf = pdf_bytes[:4] == b"%PDF"
        size   = len(pdf_bytes)
        if is_pdf and size > 1000:
            log(PASS, f"E2E:{label}", f"Download OK: {size} bytes, valid PDF")
        else:
            log(FAIL, f"E2E:{label}", f"Bad download: {size} bytes, PDF={is_pdf}")
    except Exception as e:
        log(FAIL, f"E2E:{label}", f"Download failed: {e}")

    # Cleanup test records
    Documento.objects.filter(pago=pago).delete()
    pago.delete()
    alumno.delete()
    try:
        pagador.delete()
    except Exception:
        pass
    try:
        grupo.delete()
    except Exception:
        pass
    log(PASS, f"E2E:{label}", "Test records cleaned up")

if service:
    run_e2e_test("camiandco", "Cami&Co")
    run_e2e_test("rangers",   "Rangers")
else:
    log(FAIL, "E2E", "Skipped - Drive auth failed")


# ── 9. FINAL DOWNLOAD VERIFY ─────────────────────────────────────────────────
print("\n=== 9. DOWNLOAD VERIFY (existing docs) ===")
if service:
    test_doc = Documento.objects.filter(s3_key__gt="").order_by("-id").first()
    if test_doc:
        try:
            from googleapiclient.http import MediaIoBaseDownload
            request    = service.files().get_media(fileId=test_doc.s3_key)
            buf        = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            pdf_bytes = buf.getvalue()
            is_pdf = pdf_bytes[:4] == b"%PDF"
            size   = len(pdf_bytes)
            if is_pdf and size > 1000:
                log(PASS, "Download", f"{test_doc.nombre} - {size} bytes, valid PDF header")
            else:
                log(FAIL, "Download", f"{test_doc.nombre} - {size} bytes, PDF header={'YES' if is_pdf else 'NO'}")
        except Exception as e:
            log(FAIL, "Download", f"Error downloading {test_doc.nombre}: {e}")
    else:
        log(WARN, "Download", "No persistent docs with s3_key (all were test docs, cleaned up)")
else:
    log(FAIL, "Download", "Skipped - Drive auth failed")


# ── SUMMARY ──────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
passes = sum(1 for r in results if r[0] == PASS)
warns  = sum(1 for r in results if r[0] == WARN)
fails  = sum(1 for r in results if r[0] == FAIL)
print(f"  PASS: {passes}  WARN: {warns}  FAIL: {fails}")
for status, section, msg in results:
    if status != PASS:
        print(f"  [{status}] {section}: {msg}")
print("="*60)
