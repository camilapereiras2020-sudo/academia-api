
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from django.http import FileResponse
from .models import Documento
from .serializers import DocumentoSerializer
import os


class DocumentoViewSet(ModelViewSet):
    serializer_class = DocumentoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Documento.objects.filter(academia=self.request.user)
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
        tipo = request.data.get("tipo", "factura")

        if not pago_id:
            return Response({"error": "pago_id es obligatorio"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pago = Pago.objects.select_related(
                "pagador", "alumno", "grupo", "academia"
            ).get(id=pago_id, academia=request.user)
        except Pago.DoesNotExist:
            return Response({"error": "Pago no encontrado"}, status=status.HTTP_404_NOT_FOUND)

        try:
            num_doc, file_path = generate_invoice_for_pago(pago, tipo)
        except Exception as e:
            return Response(
                {"error": f"Error generando documento: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        doc = Documento.objects.create(
            academia=request.user,
            pago=pago,
            tipo=tipo,
            nombre=os.path.basename(file_path),
            num_doc=num_doc,
            local_path=file_path,
            mime_type="application/pdf",
        )

        if not pago.num_doc:
            pago.num_doc = num_doc
            pago.save(update_fields=["num_doc"])

        return Response(DocumentoSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="descargar")
    def descargar(self, request, pk=None):
        doc = self.get_object()
        path = doc.local_path
        if path and os.path.exists(path):
            return FileResponse(
                open(path, "rb"),
                content_type=doc.mime_type,
                as_attachment=True,
                filename=doc.nombre,
            )
        docx_path = path.replace(".pdf", ".docx") if path else None
        if docx_path and os.path.exists(docx_path):
            return FileResponse(
                open(docx_path, "rb"),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                as_attachment=True,
                filename=doc.nombre.replace(".pdf", ".docx"),
            )
        return Response({"error": "Archivo no encontrado"}, status=status.HTTP_404_NOT_FOUND)

    def destroy(self, request, *args, **kwargs):
        doc = self.get_object()

        # Remove from Excel
        try:
            from .invoice_service import delete_from_excel
            import re
            year_match = re.search(r"-(\d{2})$", doc.num_doc or "")
            year = 2000 + int(year_match.group(1)) if year_match else None
            delete_from_excel(doc.num_doc, year)
        except Exception as e:
            print(f"Excel delete error (non-critical): {e}")

        # Delete physical files
        if doc.local_path and os.path.exists(doc.local_path):
            os.remove(doc.local_path)
        docx_path = doc.local_path.replace(".pdf", ".docx") if doc.local_path else None
        if docx_path and os.path.exists(docx_path):
            os.remove(docx_path)

        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
