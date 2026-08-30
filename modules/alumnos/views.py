from datetime import time as time_cls

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import marca_scope_for, NotReception
from modules.core.mixins import ContactableViaPagadorMixin
from .models import Alumno, FechaImportante, NotaAlumno, DatoSalud, ConsentimientoAlumno, Inscripcion
from .serializers import (
    AlumnoSerializer, AlumnoReceptionSerializer,
    FechaImportanteSerializer, NotaAlumnoSerializer,
    ConsentimientoAlumnoSerializer, DatoSaludSerializer,
)
from .services import alumnos_con_cumpleanos_proximos
from django.http import HttpResponse
from modules.documentos.legal_docs_service import RENDERERS

MAX_FOTO_BYTES = 5 * 1024 * 1024
FOTO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _parse_hora(value):
    """"HH:MM" -> time, or None (missing/blank/invalid all mean "no personal
    override" — i.e. the student attends the full class session)."""
    if not value:
        return None
    try:
        h, m = value.split(":")
        return time_cls(int(h), int(m))
    except (ValueError, AttributeError, TypeError):
        return None


def _validar_horario_personal(grupo, hora_inicio, hora_fin):
    """A student's personal window has to be a sub-range of the class's own
    session — arriving late or leaving early is fine, attending a
    completely different time isn't (that's a different class, not a
    personal-time override)."""
    if hora_inicio is None and hora_fin is None:
        return None
    if hora_inicio is None or hora_fin is None:
        return "Indica hora de inicio y de fin (o deja las dos en blanco para usar el horario completo de la clase)."
    if hora_inicio >= hora_fin:
        return "La hora de inicio debe ser anterior a la hora de fin."
    if not grupo.horarios:
        return None
    min_ini = min(h["ini"] for h in grupo.horarios)
    max_fin = max(h["fin"] for h in grupo.horarios)
    if hora_inicio.strftime("%H:%M") < min_ini or hora_fin.strftime("%H:%M") > max_fin:
        return f"El horario personal debe caer dentro del horario de la clase ({min_ini}–{max_fin})."
    return None


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

    @action(detail=True, methods=["get"], url_path="documento-legal/(?P<tipo>[^/.]+)")
    def documento_legal(self, request, pk=None, tipo=None):
        """Print-ready PDF for one legal document (consentimiento de imagen /
        política de cancelación), pre-filled with this alumno's real data.
        Reception-accessible on purpose — this is a front-desk/enrollment
        task, same access level as generating an invoice."""
        alumno = self.get_object()
        renderer = RENDERERS.get(tipo)
        if renderer is None:
            return Response(
                {"error": f"Tipo de documento desconocido: {tipo!r}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pdf_bytes = renderer(alumno)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{tipo}-{alumno.id}.pdf"'
        return response

    def get_queryset(self):
        qs = Alumno.objects.filter(academia=self.request.user.tenant).select_related(
            "pagador", "empresa"
        ).prefetch_related("grupos")
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
            qs = qs.filter(grupos__id=grupo).distinct()
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

    def _auto_link_self_pay_pagador(self, alumno, serializer):
        # Self-pay adult with no pagador explicitly supplied in this request:
        # auto-create/dedup a Pagador from the alumno's own contact data and
        # link it, instead of requiring the frontend to do a second, separate
        # (non-atomic) HTTP call. "Explicitly supplied" is checked via
        # initial_data (the raw request payload), not validated_data, so an
        # omitted key and an explicit null are both treated as "no pagador".
        if not alumno.es_adulto:
            return
        provided_pagador = serializer.initial_data.get("pagador") if hasattr(serializer, "initial_data") else None
        if provided_pagador:
            return
        if alumno.pagador_id:
            return
        from modules.pagadores.services import get_or_create_pagador
        pagador = get_or_create_pagador(
            academia=alumno.academia,
            nombre=alumno.nombre,
            telefono=alumno.telefono,
            email=alumno.email,
        )
        alumno.pagador = pagador
        alumno.save(update_fields=["pagador"])

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
            alumno = serializer.save(academia=self.request.user.tenant, marca=scope)
        else:
            alumno = serializer.save(academia=self.request.user.tenant)
        self._auto_link_self_pay_pagador(alumno, serializer)

    def perform_update(self, serializer):
        scope = marca_scope_for(self.request.user)
        if scope:
            provided = serializer.validated_data.get("marca")
            if provided and provided != scope:
                raise PermissionDenied(f"Solo podés editar alumnos de la marca {scope}.")
            alumno = serializer.save(marca=scope)
        else:
            alumno = serializer.save()
        self._auto_link_self_pay_pagador(alumno, serializer)

    def perform_destroy(self, instance):
        if self.request.user.role == "reception":
            raise PermissionDenied("No tenés permiso para eliminar alumnos.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="agregar-grupo")
    def agregar_grupo(self, request, pk=None):
        """Add this alumno to one more class, without touching any of their other
        memberships — a student can be in Cami's Tuesday group AND Cande's Thursday
        group at the same time (the Horario builder's drag-to-assign relies on this
        being additive, not a replace)."""
        alumno = self.get_object()
        grupo_id = request.data.get("grupo_id")
        if not grupo_id:
            return Response({"error": "Falta grupo_id"}, status=status.HTTP_400_BAD_REQUEST)
        from modules.grupos.models import Grupo
        try:
            grupo = Grupo.objects.get(id=grupo_id, academia=request.user.tenant)
        except Grupo.DoesNotExist:
            return Response({"error": "Grupo no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        if grupo.marca != alumno.marca:
            return Response(
                {"error": f"{alumno.nombre} es de {alumno.get_marca_display()} — '{grupo.nombre}' es de {grupo.get_marca_display()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        hora_inicio = _parse_hora(request.data.get("hora_inicio"))
        hora_fin = _parse_hora(request.data.get("hora_fin"))
        error = _validar_horario_personal(grupo, hora_inicio, hora_fin)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        alumno.grupos.add(grupo, through_defaults={"hora_inicio": hora_inicio, "hora_fin": hora_fin})
        return Response(self.get_serializer(alumno).data)

    @action(detail=True, methods=["post"], url_path="quitar-grupo")
    def quitar_grupo(self, request, pk=None):
        alumno = self.get_object()
        grupo_id = request.data.get("grupo_id")
        if not grupo_id:
            return Response({"error": "Falta grupo_id"}, status=status.HTTP_400_BAD_REQUEST)
        alumno.grupos.remove(grupo_id)
        return Response(self.get_serializer(alumno).data)

    @action(detail=True, methods=["post"], url_path="horario-personal")
    def horario_personal(self, request, pk=None):
        """Set/reset one existing membership's personal window — the
        drag-resize (or type-the-times-in) path in the Horario builder for a
        student who doesn't stay the whole class session. Pass hora_inicio/
        hora_fin as null (or omit them) to reset back to the full class
        time."""
        alumno = self.get_object()
        grupo_id = request.data.get("grupo_id")
        if not grupo_id:
            return Response({"error": "Falta grupo_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            insc = Inscripcion.objects.select_related("grupo").get(alumno=alumno, grupo_id=grupo_id)
        except Inscripcion.DoesNotExist:
            return Response({"error": "El alumno no está en ese grupo."}, status=status.HTTP_404_NOT_FOUND)
        hora_inicio = _parse_hora(request.data.get("hora_inicio"))
        hora_fin = _parse_hora(request.data.get("hora_fin"))
        error = _validar_horario_personal(insc.grupo, hora_inicio, hora_fin)
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        insc.hora_inicio = hora_inicio
        insc.hora_fin = hora_fin
        insc.save(update_fields=["hora_inicio", "hora_fin"])
        return Response(self.get_serializer(alumno).data)

    @action(detail=True, methods=["post"], url_path="duplicar")
    def duplicar(self, request, pk=None):
        alumno = self.get_object()
        nuevo = Alumno.objects.create(
            academia=request.user.tenant,
            nombre=f"{alumno.nombre} (copia)",
            marca=alumno.marca,
            fecha_nacimiento=alumno.fecha_nacimiento,
            pagador=alumno.pagador,
            empresa=alumno.empresa,
            es_fundae=alumno.es_fundae,
            es_adulto=alumno.es_adulto,
            nivel=alumno.nivel,
            notas=alumno.notas,
            activo=alumno.activo,
        )
        for insc in alumno.inscripciones.all():
            Inscripcion.objects.create(
                alumno=nuevo, grupo=insc.grupo, hora_inicio=insc.hora_inicio, hora_fin=insc.hora_fin,
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

