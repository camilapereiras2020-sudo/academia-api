# Changelog — academia_api

## 2026-05-27

### New modules
- Added `modules.crm` — CRM/leads management (models, views, serializers, URLs)
- Added `modules.empresas` — Companies/business clients (models, views, serializers, URLs)
- Added `modules.placement_test` — Level placement tests (models, views, serializers, URLs)

### config/settings.py
- Registered `modules.empresas` in `LOCAL_APPS` (was wired in URLs but missing from `INSTALLED_APPS`, causing startup errors)

### config/urls.py
- Removed duplicate `include("modules.placement_test.urls")` entry

### modules/pagos — Invoice/receipt number generation
- `views.py`: added `_next_num_doc(user, serie_id)` — generates sequential numbers per series per year from the DB (`CC-2026-001`, `REC-2026-001`), independent sequences for each prefix
- `views.py`: `perform_create` now determines `serie_id` from the payment method — `bizum` and `transferencia` produce a **factura** number (`CC-YYYY-NNN`); all other methods (`efectivo`, etc.) produce a **recibo** number (`REC-YYYY-NNN`)
- `views.py`: num_doc is generated once at creation only — `perform_create` is the only call site; view/print/update actions never touch it
- `serializers.py`: added `serie_id` to `read_only_fields` — clients cannot override the server-assigned series

### modules/alumnos
- Updated model, serializer, and views (grupo assignment, search, cumpleaños endpoint)

### modules/grupos
- Updated model (added `precio_hora`, `tipo_cobro`) and serializer

### modules/documentos
- Added `invoice_service.py` — PDF/DOCX invoice generation, Excel log integration
- Updated model (added `num_doc`, `local_path` fields)
- Updated `views.py`: `generar` action uses `pago.num_doc` when already set (never regenerates); added `descargar` and `destroy` actions
- `destroy` removes physical files and cleans the Excel log on delete

### modules/pagos — additional
- `models.py`: added `horas_trabajadas` field
- `pagos_views.py`: alternative viewset with Stripe integration (not currently routed)

### Migrations
- `alumnos/0002` — grupo assignment through `AlumnoGrupo` join table
- `grupos/0002` — added `precio_hora`, `tipo_cobro`
- `documentos/0002` — added `num_doc`, `local_path`; relaxed `s3_key` to blank=True
- `pagos/0002` — added `horas_trabajadas`
