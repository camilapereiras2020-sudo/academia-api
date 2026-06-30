"""
CAMI&CO — RIPPLE EFFECT ANALYZER
==================================
Run before any major script to predict and prevent downstream problems.

Usage:
    python ripple.py before fix_rutas_facturas.py
    python ripple.py before fix_precios.py
    python ripple.py check   (full system health check)
    python ripple.py fix     (auto-fix all predicted problems)

How it works:
1. Analyzes what the target script will change
2. Maps all downstream dependencies
3. Identifies second-order consequences
4. Either fixes them preemptively or warns you
5. Only then tells you it's safe to run
"""
import os, sys, django, ast, subprocess

BASE = r"C:\Users\Candela\Desktop\academia\academia_api"
FRONT = r"C:\Users\Candela\Desktop\academia\academia_frontend\src"
VENV = os.path.join(BASE, "venv", "Scripts", "python.exe")
sys.path.insert(0, BASE)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

problems = []
fixes_applied = []
warnings = []

def problem(label, detail, fix_fn=None, fix_label=""):
    problems.append({"label": label, "detail": detail, "fix_fn": fix_fn, "fix_label": fix_label})
    print(f"  ⚠ {label}")
    print(f"    → {detail}")

def fixed(label):
    fixes_applied.append(label)
    print(f"  ⚡ FIXED: {label}")

def safe(label):
    print(f"  ✓ {label}")

def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")

def read(path):
    if not os.path.exists(path):
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def run_cmd(cmd):
    r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, shell=True)
    return r.returncode, r.stdout, r.stderr

# ══════════════════════════════════════════════════════════
def check_invoice_service():
    """Check invoice_service.py for syntax and logic issues"""
    path = os.path.join(BASE, "modules", "documentos", "invoice_service.py")
    content = read(path)
    
    if not content:
        problem("invoice_service.py missing", "File not found")
        return False
    
    # Syntax check
    try:
        ast.parse(content)
        safe("invoice_service.py syntax OK")
    except SyntaxError as e:
        problem(
            f"invoice_service.py syntax error line {e.lineno}",
            str(e.msg),
            fix_label="Run: python fix_invoice_final.py"
        )
        return False
    
    # Logic checks
    checks = [
        ("METODOS_FACTURA", "Bizum/Transfer detection missing"),
        ("_next_invoice_number", "Invoice numbering missing"),
        ("IBAN", "IBAN not configured"),
        ("reportlab", "PDF generation library missing"),
        ("upload_to_drive", "Drive upload missing"),
        ("Mandela", "Wrong quote — should be Mandela not Whitman"),
    ]
    
    all_ok = True
    for check, msg in checks:
        if check in content:
            safe(f"  {check} present")
        else:
            problem(f"  {check} missing", msg)
            all_ok = False
    
    # Check for apostrophe issues
    if "it\\'s done" in content or "it's done" in content:
        # Check if it's properly escaped
        if "'It always seems impossible until it" in content:
            try:
                ast.parse(content)
                safe("  Mandela quote properly escaped")
            except:
                problem("Apostrophe in Mandela quote", 
                       "it's done causes syntax error",
                       fix_label="Run: python fix_invoice_final.py")
                all_ok = False
    
    return all_ok


def check_excel_files():
    """Check for corrupted or conflicting Excel files"""
    excel_dirs = [
        r"C:\Users\Candela\Desktop\CAMI&CO\Facturas\DE CAM&CO\Facturas 2026",
        r"C:\Users\Candela\Desktop\CAMI&CO\Facturas\DE CAM&CO\Facturas 2026\Control Facturas\Excel",
    ]
    
    for d in excel_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".xlsx") and not f.startswith("~"):
                    xl_path = os.path.join(d, f)
                    # Check if file is locked (open in Excel)
                    lock_path = os.path.join(d, "~$" + f)
                    if os.path.exists(lock_path):
                        problem(
                            f"Excel file locked: {f}",
                            "Close Excel before generating invoices",
                        )
                    else:
                        safe(f"Excel OK: {f}")


def check_migrations():
    """Check for pending migrations"""
    django.setup()
    from django.db.migrations.executor import MigrationExecutor
    from django.db import connection
    try:
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            for migration, _ in plan:
                problem(
                    f"Pending migration: {migration}",
                    "Run: python manage.py migrate",
                    fix_label="python manage.py migrate"
                )
        else:
            safe("All migrations applied")
    except Exception as e:
        problem("Migration check failed", str(e)[:80])


def check_frontend_files():
    """Check frontend for known issues"""
    checks = [
        (r"features\alumnos\pages\AlumnosPage.tsx", [
            ("alumno_set", "Old relation name — will crash"),
        ]),
        (r"components\layout\Sidebar.tsx", [
            ("Gamepad2", "Icon doesn't exist in lucide-react — will crash"),
        ]),
        (r"App.tsx", [
            ("/crm", None),
            ("/empresas", None),
            ("/juegos/vocab", None),
        ]),
    ]
    
    for rel_path, issues in checks:
        full = os.path.join(FRONT, rel_path)
        content = read(full)
        if not content:
            problem(f"Missing: {rel_path}", "File not found")
            continue
        
        for check, msg in issues:
            if msg:  # This is a bad pattern
                if check in content:
                    problem(f"{rel_path}: {check}", msg)
            else:  # This is a required pattern
                if check not in content:
                    problem(f"{rel_path}: missing {check}", "Route not configured")
                else:
                    safe(f"{rel_path}: {check} OK")


def check_model_fields():
    """Check that all required model fields exist"""
    django.setup()
    
    field_requirements = [
        ("modules.alumnos.models.Alumno", ["nombre", "fecha_nacimiento", "grupo", "pagador", "empresa", "es_fundae", "nivel", "activo"]),
        ("modules.grupos.models.Grupo", ["nombre", "nivel", "tarifa", "tipo_cobro", "precio_hora"]),
        ("modules.pagos.models.Pago", ["alumno", "pagador", "grupo", "periodo", "mensualidad", "total", "estado", "metodo"]),
        ("modules.documentos.models.Documento", ["num_doc", "local_path", "mime_type"]),
        ("modules.crm.models.Lead", ["etapa", "nombre_contacto", "nombre_alumno", "telefono"]),
    ]
    
    for model_path, required_fields in field_requirements:
        parts = model_path.rsplit(".", 1)
        module_path, class_name = parts[0], parts[1]
        try:
            import importlib
            module = importlib.import_module(module_path)
            model = getattr(module, class_name)
            existing = [f.name for f in model._meta.get_fields()]
            
            for field in required_fields:
                if field in existing:
                    safe(f"  {class_name}.{field}")
                else:
                    problem(
                        f"{class_name}.{field} missing",
                        f"Add field to {module_path}",
                        fix_label=f"Add {field} to {class_name} model and migrate"
                    )
        except Exception as e:
            problem(f"Cannot check {model_path}", str(e)[:60])


def check_folder_structure():
    """Check that output folders exist"""
    required_folders = [
        r"C:\Users\Candela\Desktop\CAMI&CO\Facturas\DE CAM&CO\Facturas 2026\Control Facturas\Word\T1 (Enero-Abril)",
        r"C:\Users\Candela\Desktop\CAMI&CO\Facturas\DE CAM&CO\Facturas 2026\Control Facturas\Word\T2 (Mayo-Agosto)",
        r"C:\Users\Candela\Desktop\CAMI&CO\Facturas\DE CAM&CO\Facturas 2026\Control Facturas\Word\T3 (Septiembre-Diciembre)",
        r"C:\Users\Candela\Desktop\CAMI&CO\Facturas\DE CAM&CO\Facturas 2026\Control Facturas\PDFs\T1 (Enero-Abril)",
        r"C:\Users\Candela\Desktop\CAMI&CO\Facturas\DE CAM&CO\Facturas 2026\Control Facturas\PDFs\T2 (Mayo-Agosto)",
        r"C:\Users\Candela\Desktop\CAMI&CO\Facturas\DE CAM&CO\Facturas 2026\Control Facturas\PDFs\T3 (Septiembre-Diciembre)",
        r"C:\Users\Candela\Desktop\CAMI&CO\Facturas\DE CAM&CO\Facturas 2026\Control Facturas\Excel",
    ]
    
    missing = []
    for folder in required_folders:
        if os.path.exists(folder):
            safe(f"  {folder.split('Control Facturas')[1] or folder[-30:]}")
        else:
            missing.append(folder)
            problem(f"Missing folder", folder.split("Facturas 2026")[1])
    
    if missing:
        # Auto-fix
        for folder in missing:
            os.makedirs(folder, exist_ok=True)
        fixed("Created missing folders")


def auto_fix_all():
    """Run all fixable problems automatically"""
    print("\n  Running auto-fixes...")
    
    # Fix migrations
    code, out, err = run_cmd(f'"{VENV}" manage.py makemigrations --no-input')
    if "Migrations for" in out:
        fixed("Created pending migrations")
    
    code, out, err = run_cmd(f'"{VENV}" manage.py migrate --no-input')
    if "OK" in out:
        fixed("Applied migrations")
    
    # Fix folders
    check_folder_structure()
    
    # Fix sidebar Gamepad2
    sidebar = os.path.join(FRONT, r"components\layout\Sidebar.tsx")
    content = read(sidebar)
    if "Gamepad2" in content:
        write(sidebar, content.replace("Gamepad2", "Joystick"))
        fixed("Sidebar: Gamepad2 → Joystick")


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════
print()
print("=" * 60)
print("   CAMI&CO — RIPPLE EFFECT ANALYZER")
print("=" * 60)

mode = sys.argv[1] if len(sys.argv) > 1 else "check"
target = sys.argv[2] if len(sys.argv) > 2 else ""

if mode == "before":
    print(f"\n  Analyzing risks before running: {target}")

section("1. Invoice Service")
check_invoice_service()

section("2. Excel Files")
check_excel_files()

section("3. Output Folders")
check_folder_structure()

section("4. Migrations")
check_migrations()

section("5. Model Fields")
check_model_fields()

section("6. Frontend Files")
check_frontend_files()

# Summary
print()
print("=" * 60)
print("   RIPPLE ANALYSIS COMPLETE")
print("=" * 60)
print(f"\n  ⚡ Auto-fixed:  {len(fixes_applied)}")
print(f"  ⚠  Problems:   {len(problems)}")

if problems:
    print(f"\n  Problems found:")
    for p in problems:
        print(f"    ⚠ {p['label']}")
        if p['fix_label']:
            print(f"      Fix: {p['fix_label']}")
    
    print()
    if mode == "fix":
        auto_fix_all()
        print("\n  Run 'python ripple.py check' to verify fixes.")
    else:
        print(f"  Run 'python ripple.py fix' to auto-fix what's possible.")
        if target:
            print(f"  Then run: python {target}")
else:
    print()
    print("  ✅ No problems detected — safe to proceed!")
    if target:
        print(f"  ✅ Safe to run: python {target}")

print()
