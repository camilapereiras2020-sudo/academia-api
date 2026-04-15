from rest_framework import serializers
from .models import Documento

class DocumentoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Documento
        fields = ["id", "pago", "tipo", "nombre", "mime_type", "url", "created_at"]
        read_only_fields = ["id", "created_at", "url"]

    def get_url(self, obj):
        import boto3
        from botocore.config import Config
        from django.conf import settings
        client = boto3.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL, aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, config=Config(signature_version="s3v4"), use_ssl=settings.AWS_S3_USE_SSL)
        return client.generate_presigned_url("get_object", Params={"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": obj.s3_key}, ExpiresIn=3600)
