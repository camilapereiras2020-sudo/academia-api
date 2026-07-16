
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from modules.authentication.rbac import marca_scope_for
from .models import Alumno
from .serializers import AlumnoSerializer, AlumnoReceptionSerializer


class AlumnoViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.user.role == "reception":
            return AlumnoReceptionSerializer
        return AlumnoSerializer

    def get_queryset(self):
        qs = Alumno.objects.filter(academia=self.request.user.tenant)
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
        from datetime import date, timedelta
        today = date.today()
        try:
            window = int(request.query_params.get("dias", 30))
        except ValueError:
            window = 30
        upcoming = []
        for alumno in self.get_queryset():
            if alumno.fecha_nacimiento:
                bd = alumno.fecha_nacimiento.replace(year=today.year)
                if bd < today:
                    bd = bd.replace(year=today.year + 1)
                days = (bd - today).days
                if days <= window:
                    upcoming.append({
                        "id": alumno.id,
                        "nombre": alumno.nombre,
                        "fecha_nacimiento": alumno.fecha_nacimiento,
                        "dias_para_cumpleanos": days,
                    })
        return Response(sorted(upcoming, key=lambda x: x["dias_para_cumpleanos"]))

    @action(detail=True, methods=["post"], url_path="enviar-email")
    def enviar_email(self, request, pk=None):
        from modules.core.email_service import send_email
        alumno = self.get_object()
        pagador = alumno.pagador
        if not pagador or not pagador.email:
            return Response(
                {"error": "Este alumno no tiene un pagador con email registrado"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        asunto = request.data.get("asunto", "")
        cuerpo = request.data.get("cuerpo", "")
        if not asunto or not cuerpo:
            return Response(
                {"error": "asunto y cuerpo son obligatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            msg_id = send_email(
                to=pagador.email,
                subject=asunto,
                body=cuerpo,
                academia_nombre=getattr(request.user.tenant, "academia_nombre", "") or "",
            )
            return Response({"ok": True, "id": msg_id, "enviado_a": pagador.email})
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["get"], url_path="whatsapp-link")
    def whatsapp_link(self, request, pk=None):
        from modules.core.whatsapp_service import whatsapp_link
        alumno = self.get_object()
        pagador = alumno.pagador
        if not pagador or not pagador.telefono:
            return Response(
                {"error": "Este alumno no tiene un pagador con teléfono registrado"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        texto = request.query_params.get("texto", "")
        return Response({"url": whatsapp_link(pagador.telefono, texto), "enviado_a": pagador.telefono})
