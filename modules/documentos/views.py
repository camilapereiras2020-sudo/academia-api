from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework.viewsets import ModelViewSet
from .models import Documento
from .serializers import DocumentoSerializer
import uuid

class DocumentoViewSet(ModelViewSet):
    serializer_class = DocumentoSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def get_queryset(self):
        return Documento.objects.filter(academia=self.request.user)

    def create(self, request, *args, **kwargs):
        import boto3
        from botocore.config import Config
        from django.conf import settings
        file = request.FILES.get("file")
        nombre = request.data.get("nombre", file.name if file else "documento")
        tipo = request.data.get("tipo", "otro")
        pago_id = request.data.get("pago")
        client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, config=Config(signature_version="s3v4"), use_ssl=settings.AWS_S3_USE_SSL)
        key = f"{request.user.id}/{tipo}/{uuid.uuid4()}/{nombre}"
        client.upload_fileobj(file, settings.AWS_STORAGE_BUCKET_NAME, key, ExtraArgs={"ContentType": file.content_type})
        doc = Documento.objects.create(academia=request.user, pago_id=pago_id, tipo=tipo, nombre=nombre, s3_key=key, mime_type=file.content_type)
        return Response(DocumentoSerializer(doc).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        import boto3
        from botocore.config import Config
        from django.conf import settings
        doc = self.get_object()
        client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, config=Config(signature_version="s3v4"), use_ssl=settings.AWS_S3_USE_SSL)
        client.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=doc.s3_key)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
