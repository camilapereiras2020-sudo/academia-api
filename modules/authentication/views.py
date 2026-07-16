from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import RegisterSerializer, UserProfileSerializer
from .permissions import IsOwner

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [IsOwner]

    def perform_create(self, serializer):
        role = serializer.validated_data.get("role", "owner")
        academia_owner = self.request.user if role != "owner" else None
        serializer.save(academia_owner=academia_owner)

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        if self.request.user.role == "reception" and any(
            field in self.request.data for field in UserProfileSerializer.ACADEMIA_FIELDS
        ):
            raise PermissionDenied("No tenés permiso para editar los datos de la academia.")
        serializer.save()
