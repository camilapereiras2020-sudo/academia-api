from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework import generics, permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from .models import Aviso, AvisoLectura, AvisoMensaje
from .serializers import AvisoMensajeSerializer, AvisoSerializer

User = get_user_model()


class IsCreatorOrRecipient(permissions.IsAuthenticated):
    """Anyone in the tenant can read (queryset already scopes that); only
    the person who created an aviso or the one it's addressed to can change
    or delete it — e.g. mark their own note as read, or edit/remove a task
    they made."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # Participantes: quien lo creó, a quien va dirigido, o cualquiera del
        # equipo si es un aviso para todos.
        return (
            obj.creado_por_id == request.user.id
            or obj.para_id == request.user.id
            or obj.para_todos
        )


class AvisoViewSet(ModelViewSet):
    serializer_class = AvisoSerializer
    permission_classes = [IsCreatorOrRecipient]

    def get_queryset(self):
        user = self.request.user
        tenant_id = user.tenant.id
        ultimo_mensaje = AvisoMensaje.objects.filter(aviso=OuterRef("pk")).order_by("-created_at", "-id")
        qs = Aviso.objects.filter(academia_id=tenant_id).select_related("creado_por", "para").annotate(
            mensajes_count=Count("mensajes", distinct=True),
            ultimo_texto=Subquery(ultimo_mensaje.values("texto")[:1]),
            # "No leído" = lo último que pasó en el hilo no es mío y no lo he
            # abierto desde entonces.
            no_leido=~Q(ultimo_autor_id=user.id) & ~Exists(
                AvisoLectura.objects.filter(aviso=OuterRef("pk"), user=user, leido_hasta__gte=OuterRef("ultima_actividad"))
            ),
        )

        if self.request.query_params.get("para_mi"):
            # Lo que tengo pendiente de leer: hilos abiertos míos (o de todo el
            # equipo) donde lo último lo escribió otra persona.
            return qs.filter(
                Q(para_id=user.id) | Q(para_todos=True) | Q(creado_por_id=user.id),
                hecha=False, no_leido=True,
            )

        desde = self.request.query_params.get("desde")
        hasta = self.request.query_params.get("hasta")
        if desde or hasta:
            qs = qs.filter(fecha__isnull=False)
            if desde:
                qs = qs.filter(fecha__gte=desde)
            if hasta:
                qs = qs.filter(fecha__lte=hasta)
            return qs

        # Default (no filter): everything relevant to this user — tasks on
        # the shared calendar plus notes they sent or received.
        return qs.filter(
            Q(fecha__isnull=False) | Q(para_id=user.id) | Q(creado_por_id=user.id) | Q(para_todos=True)
        )

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(academia_id=user.tenant.id, creado_por=user, ultimo_autor=user)

    @staticmethod
    def _marcar_leido(aviso, user):
        AvisoLectura.objects.update_or_create(
            aviso=aviso, user=user,
            defaults={"leido_hasta": max(timezone.now(), aviso.ultima_actividad)},
        )

    @action(detail=True, methods=["get", "post"], url_path="mensajes")
    def mensajes(self, request, pk=None):
        """GET: el hilo (respuestas, de más antigua a más reciente) — y lo
        marca como leído. POST {texto}: contesta; si el aviso estaba resuelto
        lo reabre y vuelve a salir como pendiente para el resto."""
        aviso = self.get_object()
        if request.method == "GET":
            self._marcar_leido(aviso, request.user)
            qs = aviso.mensajes.select_related("autor")
            return Response(AvisoMensajeSerializer(qs, many=True).data)

        ser = AvisoMensajeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        msg = ser.save(aviso=aviso, autor=request.user)
        aviso.ultima_actividad = msg.created_at
        aviso.ultimo_autor = request.user
        aviso.hecha = False
        aviso.save(update_fields=["ultima_actividad", "ultimo_autor", "hecha"])
        self._marcar_leido(aviso, request.user)
        return Response(AvisoMensajeSerializer(msg).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="leido")
    def leido(self, request, pk=None):
        """Marca el hilo como leído por mí (sin resolverlo para los demás)."""
        aviso = self.get_object()
        self._marcar_leido(aviso, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class EquipoUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]


class EquipoListView(generics.ListAPIView):
    """Every login account in the requester's tenant (the owner plus any
    co_manager/reception staff accounts) — used to pick who a task or note
    is for."""
    serializer_class = EquipoUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant_id = self.request.user.tenant.id
        return User.objects.filter(Q(pk=tenant_id) | Q(academia_owner_id=tenant_id)).order_by("username")
