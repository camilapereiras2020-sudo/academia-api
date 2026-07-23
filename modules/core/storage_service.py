import io

from googleapiclient.http import MediaIoBaseUpload

from modules.documentos.invoice_service import _drive, _folder


def upload_alumno_foto(file_bytes: bytes, filename: str, mimetype: str) -> str:
    """Upload a student photo to a top-level "Fotos Alumnos" Drive folder (not nested
    under any Emisor's invoice folder) and return a publicly link-viewable image URL.

    Unlike invoices — which stay private and are proxied through
    DocumentoViewSet.descargar — profile photos are made link-shareable so the frontend
    can use foto_url directly as an <img src>. Reuses the same OAuth2 Drive credentials
    invoices already upload through (see invoice_service._credentials): a service account
    has no storage quota on this Drive and cannot upload new files.
    """
    service = _drive()
    folder_id = _folder(service, "Fotos Alumnos")

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype, resumable=False)
    file = service.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id",
    ).execute()
    file_id = file["id"]

    service.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w512"
