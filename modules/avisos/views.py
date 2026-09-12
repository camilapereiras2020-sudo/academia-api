from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, permissions, serializers
from rest_framework.viewsets import ModelViewSet
from .models import Aviso
from .serializers import AvisoSerializer

User = get_user_model()


class IsCreatorOrRecipient(permissions.IsAuthenticated):
    """Anyone in the tenant can read (queryset already scopes that); only
    the person who created an aviso or the one it's addressed to can change
    or delete it — e.g. mark their own note as read, or edit/remove a task
    they made."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.creado_por_id == request.user.id or obj.para_id == request.user.id


class AvisoViewSet(ModelViewSet):
    serializer_class = AvisoSerializer
    permission_classes = [IsCreatorOrRecipient]

    def get_queryset(self):
        user = self.request.user
        tenant_id = user.tenant.id
        qs = Aviso.objects.filter(academia_id=tenant_id)

        if self.request.query_params.get("para_mi"):
            return qs.filter(para_id=user.id, hecha=False)

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
            Q(fecha__isnull=False) | Q(para_id=user.id) | Q(creado_por_id=user.id)
        )

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(academia_id=user.tenant.id, creado_por=user)


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
