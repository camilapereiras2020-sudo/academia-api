import os

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from modules.authentication.rbac import marca_scope_for
from .models import Documento
from .serializers import DocumentoSerializer


class DocumentoViewSet(ModelViewSet):
    serializer_class   = DocumentoSerializer
    # reception is allowed here (unlike most viewsets) so she can generate
    # and download invoices/recibos for existing pagos — but destroy/anular
    # below are explicitly blocked for her, those are financial/admin-only.
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs   = Documento.objects.filter(academia=self.request.user.tenant).select_related(
            "pago", "pago__alumno", "pago__pagador"
        )
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(pago__marca=scope)
        pago = self.request.query_params.get("pago")
        tipo = self.request.query_params.get("tipo")
        if pago:
            qs = qs.filter(pago_id=pago)
        if tipo:
            qs = qs.filter(tipo=tipo)
        return qs

    @action(detail=False, methods=["post"], url_path="generar")
    def generar(self, request):
        from modules.pagos.models import Pago
        from .invoice_service import generate_invoice_for_pago

        pago_id = request.data.get("pago_id")

        if not pago_id:
            return Response({"error": "pago_id es obligatorio"}, status=status.HTTP_400_BAD_REQUEST)

        pago_qs = Pago.objects.select_related("pagador", "alumno", "grupo", "academia").filter(
            academia=request.user.tenant
        )
        scope = marca_scope_for(request.user)
        if scope:
            pago_qs = pago_qs.filter(marca=scope)
        try:
            pago = pago_qs.get(id=pago_id)
        except Pago.DoesNotExist:
            return Response({"error": "Pago no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        # Idempotent: a non-borrador Documento already means this pago's real
        # invoice/receipt exists — return it instead of minting a new num_doc
        # (double-click, retry-after-partial-failure, etc. must not duplicate).
        existing = pago.documentos.filter(estado="emitida").order_by("-created_at").first()
        if existing:
            return Response(DocumentoSerializer(existing).data, status=status.HTTP_200_OK)

        try:
            num_doc, drive_id, tipo = generate_invoice_for_pago(pago)
        except ValueError as e:
            # incomplete/misconfigured pago — a predictable client error, not a server fault
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Error generando documento: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        doc = Documento.objects.create(
            academia   = request.user.tenant,
            pago       = pago,
            tipo       = tipo,
            nombre     = f"{num_doc}.pdf",
            num_doc    = num_doc,
            s3_key     = drive_id,       # Drive file id stored here
            local_path = "",
            mime_type  = "application/pdf",
            estado     = "emitida",
            emitida_at = timezone.now(),
        )

        pago.num_doc = num_doc
        pago.save(update_fields=["num_doc"])

        try:
            from .sheets_log import log_emision
            log_emision(doc)
        except Exception as e:
            print(f"[generar] sheet log failed (non-critical): {e}")

        return Response(DocumentoSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="descargar")
    def descargar(self, request, pk=None):
        doc = self.get_object()

        # ── Google Drive (new path) ─────────────────────────────────────────
        if doc.s3_key:
            try:
                from .invoice_service import download_from_drive
                pdf_bytes = download_from_drive(doc.s3_key)
                response  = HttpResponse(pdf_bytes, content_type="application/pdf")
                response["Content-Disposition"] = f'inline; filename="{doc.nombre}"'
                return response
            except Exception as e:
                return Response(
                    {"error": f"Error descargando desde Drive: {str(e)}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        # ── Local file fallback (legacy docs) ───────────────────────────────
        from django.http import FileResponse
        path = doc.local_path
        if path and os.path.exists(path):
            return FileResponse(
                open(path, "rb"),
                content_type=doc.mime_type,
                as_attachment=False,
                filename=doc.nombre,
            )
        docx = path.replace(".pdf", ".docx") if path else None
        if docx and os.path.exists(docx):
            return FileResponse(
                open(docx, "rb"),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=False,
                filename=doc.nombre.replace(".pdf", ".docx"),
            )

        return Response({"error": "Archivo no encontrado"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, *args, **kwargs):
        if request.user.role == "reception":
            raise PermissionDenied("No tenés permiso para eliminar documentos.")
        doc = self.get_object()

        if doc.is_issued:
            return Response(
                {"error": "Este documento ya está emitido: no se puede eliminar, solo anular."},
                status=status.HTTP_409_CONFLICT,
            )

        # borrador only — never had a Drive/local file to clean up
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="anular")
    def anular(self, request, pk=None):
        if request.user.role == "reception":
            raise PermissionDenied("No tenés permiso para anular documentos.")
        doc = self.get_object()
        if doc.estado == "anulada":
            return Response({"error": "Este documento ya está anulado."}, status=status.HTTP_400_BAD_REQUEST)
        if not doc.is_issued:
            return Response({"error": "Un borrador se elimina, no se anula."}, status=status.HTTP_400_BAD_REQUEST)

        motivo = (request.data.get("motivo_anulacion") or "").strip()
        if not motivo:
            return Response({"error": "motivo_anulacion es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        from .invoice_service import regenerate_anulada_pdf
        try:
            new_drive_id = regenerate_anulada_pdf(doc)
        except Exception as e:
            return Response(
                {"error": f"Error regenerando PDF anulado: {e}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        doc.estado           = "anulada"
        doc.anulada_at       = timezone.now()
        doc.motivo_anulacion = motivo
        doc.s3_key           = new_drive_id
        doc.save(update_fields=["estado", "anulada_at", "motivo_anulacion", "s3_key"])

        try:
            from .sheets_log import log_anulacion
            log_anulacion(doc)
        except Exception as e:
            print(f"[anular] sheet log failed (non-critical): {e}")

        return Response(DocumentoSerializer(doc).data)
