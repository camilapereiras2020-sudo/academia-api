import os

from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Documento
from .serializers import DocumentoSerializer


class DocumentoViewSet(ModelViewSet):
    serializer_class   = DocumentoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs   = Documento.objects.filter(academia=self.request.user)
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
        tipo    = request.data.get("tipo", "factura")

        if not pago_id:
            return Response({"error": "pago_id es obligatorio"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pago = Pago.objects.select_related(
                "pagador", "alumno", "grupo", "academia"
            ).get(id=pago_id, academia=request.user)
        except Pago.DoesNotExist:
            return Response({"error": "Pago no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        try:
            num_doc, drive_id = generate_invoice_for_pago(pago, tipo)
        except Exception as e:
            return Response(
                {"error": f"Error generando documento: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        doc = Documento.objects.create(
            academia   = request.user,
            pago       = pago,
            tipo       = tipo,
            nombre     = f"{num_doc}.pdf",
            num_doc    = num_doc,
            s3_key     = drive_id,       # Drive file id stored here
            local_path = "",
            mime_type  = "application/pdf",
        )

        pago.num_doc = num_doc
        pago.save(update_fields=["num_doc"])

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
                response["Content-Disposition"] = f'attachment; filename="{doc.nombre}"'
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
                as_attachment=True,
                filename=doc.nombre,
            )
        docx = path.replace(".pdf", ".docx") if path else None
        if docx and os.path.exists(docx):
            return FileResponse(
                open(docx, "rb"),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True,
                filename=doc.nombre.replace(".pdf", ".docx"),
            )

        return Response({"error": "Archivo no encontrado"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, *args, **kwargs):
        doc = self.get_object()

        # Delete from Drive
        if doc.s3_key:
            try:
                from .invoice_service import delete_drive_file
                delete_drive_file(doc.s3_key)
            except Exception as e:
                print(f"Drive delete error (non-critical): {e}")

        # Delete local file (legacy)
        if doc.local_path:
            for path in (doc.local_path, doc.local_path.replace(".pdf", ".docx")):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
