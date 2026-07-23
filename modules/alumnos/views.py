
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import marca_scope_for, NotReception
from modules.core.mixins import ContactableViaPagadorMixin
from .models import Alumno, FechaImportante, NotaAlumno, DatoSalud, ConsentimientoAlumno
from .serializers import (
    AlumnoSerializer, AlumnoReceptionSerializer,
    FechaImportanteSerializer, NotaAlumnoSerializer,
    ConsentimientoAlumnoSerializer, DatoSaludSerializer,
)
from .services import alumnos_con_cumpleanos_proximos

MAX_FOTO_BYTES = 5 * 1024 * 1024
FOTO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class TenantScopedForAlumnoMixin:
    """Shared get_queryset for the fecha-importante/nota/consentimiento ViewSets: scoped
    to the requesting tenant (and marca, for a co_manager) via the alumno FK, filterable
    by ?alumno=<id> — same query-param filtering style as modules.clases's TareaViewSet."""

    def get_queryset(self):
        qs = self.queryset_model.objects.filter(alumno__academia=self.request.user.tenant)
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(alumno__marca=scope)
        alumno_id = self.request.query_params.get("alumno")
        if alumno_id:
            qs = qs.filter(alumno_id=alumno_id)
        return qs


class AlumnoViewSet(ContactableViaPagadorMixin, ModelViewSet):
    pagador_attr = "pagador"
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.user.role == "reception":
            return AlumnoReceptionSerializer
        return AlumnoSerializer

    def get_queryset(self):
        qs = Alumno.objects.filter(academia=self.request.user.tenant).select_related(
            "pagador", "grupo", "empresa"
        )
        scope = marca_scope_for(self.request.user)
        if scope:
            qs = qs.filter(marca=scope)
        search    = self.request.query_params.get("search")
        grupo     = self.request.query_params.get("grupo")
        empresa   = self.request.query_params.get("empresa")
        es_fundae = self.request.query_params.get("es_fundae")
        tipo      = self.request.query_params.get("tipo")  # "empresa", "particular", "fundae"
        marca     = self.request.query_params.get("marca")

        if marca:
            qs = qs.filter(marca=marca)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(nombre__icontains=search) |
                Q(pagador__nombre__icontains=search)
            )
        if grupo:
            qs = qs.filter(grupo_id=grupo)
        if empresa:
            qs = qs.filter(empresa_id=empresa)
        if es_fundae is not None:
            qs = qs.filter(es_fundae=es_fundae.lower() == "true")
        if tipo == "empresa":
            qs = qs.filter(empresa__isnull=False)
        elif tipo == "particular":
            qs = qs.filter(empresa__isnull=True)
        elif tipo == "fundae":
            qs = qs.filter(es_fundae=True)
        return qs

    def perform_create(self, serializer):
        # reception can edit existing alumnos and use asignar-grupo/duplicar
        # (which create rows too, but those are explicit, narrower actions) —
        # creating a brand-new alumno from scratch is an enrollment decision,
        # out of her "contacto básico" scope.
        if self.request.user.role == "reception":
            raise PermissionDenied("No tenés permiso para crear alumnos nuevos.")
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés crear alumnos de la marca {scope}.")
            serializer.save(academia=self.request.user.tenant, marca=scope)
        else:
            serializer.save(academia=self.request.user.tenant)

    def perform_update(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés editar alumnos de la marca {scope}.")
            serializer.save(marca=scope)
        else:
            serializer.save()

    def perform_destroy(self, instance):
        if self.request.user.role == "reception":
            raise PermissionDenied("No tenés permiso para eliminar alumnos.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="asignar-grupo")
    def asignar_grupo(self, request, pk=None):
        alumno = self.get_object()
        grupo_id = request.data.get("grupo_id")
        if grupo_id:
            from modules.grupos.models import Grupo
            try:
                grupo = Grupo.objects.get(id=grupo_id, academia=request.user.tenant)
            except Grupo.DoesNotExist:
                return Response({"error": "Grupo no encontrado"}, status=status.HTTP_404_NOT_FOUND)
            alumno.grupo = grupo
        else:
            alumno.grupo = None
        alumno.save(update_fields=["grupo"])
        return Response(self.get_serializer(alumno).data)

    @action(detail=True, methods=["post"], url_path="duplicar")
    def duplicar(self, request, pk=None):
        alumno = self.get_object()
        nuevo = Alumno.objects.create(
            academia=request.user.tenant,
            nombre=f"{alumno.nombre} (copia)",
            marca=alumno.marca,
            fecha_nacimiento=alumno.fecha_nacimiento,
            grupo=alumno.grupo,
            pagador=alumno.pagador,
            empresa=alumno.empresa,
            es_fundae=alumno.es_fundae,
            nivel=alumno.nivel,
            notas=alumno.notas,
            activo=alumno.activo,
        )
        return Response(self.get_serializer(nuevo).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="cumpleanos")
    def cumpleanos(self, request):
        try:
            window = int(request.query_params.get("dias", 30))
        except ValueError:
            window = 30
        return Response(alumnos_con_cumpleanos_proximos(self.get_queryset(), window))

    @action(detail=True, methods=["get"], url_path="resumen")
    def resumen(self, request, pk=None):
        """One call replacing 4-5 separate requests from the ficha del alumno: pagos,
        fechas importantes and notas for this alumno. Health data and consents are
        deliberately never included here — they have their own gated/separate endpoints."""
        from modules.pagos.models import Pago
        from modules.pagos.serializers import PagoSerializer

        alumno = self.get_object()
        pagos = Pago.objects.filter(alumno=alumno).select_related("pagador", "grupo", "emisor", "tarifa")
        fechas = alumno.fechas_importantes.all()
        notas = alumno.notas_registro.select_related("autor").all()
        return Response({
            "pagos": PagoSerializer(pagos, many=True, context={"request": request}).data,
            "fechas_importantes": FechaImportanteSerializer(fechas, many=True, context={"request": request}).data,
            "notas": NotaAlumnoSerializer(notas, many=True, context={"request": request}).data,
        })

    @action(detail=True, methods=["post"], url_path="foto", parser_classes=[MultiPartParser])
    def foto(self, request, pk=None):
        alumno = self.get_object()
        upload = request.FILES.get("foto")
        if not upload:
            return Response({"error": "No se recibió ningún archivo."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.content_type not in FOTO_CONTENT_TYPES:
            return Response({"error": "Formato no soportado. Usa JPG, PNG o WEBP."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_FOTO_BYTES:
            return Response({"error": "La imagen supera el tamaño máximo de 5MB."}, status=status.HTTP_400_BAD_REQUEST)

        file_bytes = upload.read()
        from PIL import Image, UnidentifiedImageError
        import io as _io
        try:
            Image.open(_io.BytesIO(file_bytes)).verify()
        except UnidentifiedImageError:
            return Response({"error": "El archivo no es una imagen válida."}, status=status.HTTP_400_BAD_REQUEST)

        from modules.core.storage_service import upload_alumno_foto
        try:
            foto_url = upload_alumno_foto(file_bytes, upload.name, upload.content_type)
        except Exception as e:
            return Response({"error": f"Error al subir la foto a Drive: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

        alumno.foto_url = foto_url
        alumno.save(update_fields=["foto_url"])
        return Response(self.get_serializer(alumno).data)

    @action(detail=True, methods=["get", "put"], url_path="salud",
            permission_classes=[permissions.IsAuthenticated, NotReception])
    def salud(self, request, pk=None):
        alumno = self.get_object()
        dato, _ = DatoSalud.objects.get_or_create(alumno=alumno)
        if request.method == "GET":
            return Response(DatoSaludSerializer(dato).data)
        serializer = DatoSaludSerializer(dato, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class FechaImportanteViewSet(TenantScopedForAlumnoMixin, ModelViewSet):
    queryset_model = FechaImportante
    serializer_class = FechaImportanteSerializer
    permission_classes = [permissions.IsAuthenticated]


class NotaAlumnoViewSet(TenantScopedForAlumnoMixin, ModelViewSet):
    queryset_model = NotaAlumno
    serializer_class = NotaAlumnoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(autor=self.request.user)


class ConsentimientoAlumnoViewSet(TenantScopedForAlumnoMixin, ModelViewSet):
    queryset_model = ConsentimientoAlumno
    serializer_class = ConsentimientoAlumnoSerializer
    permission_classes = [permissions.IsAuthenticated]

