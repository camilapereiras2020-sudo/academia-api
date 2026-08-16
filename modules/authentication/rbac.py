from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission


def marca_scope_for(user):
    """The single marca a user's queries should be restricted to, or None for
    no restriction (owner, and reception — who sees both marcas).

    Fails closed: a co_manager is required to have marca_asignada set. Every
    call site treats a None return as "no restriction" (`if scope: ...`), so
    silently returning None here for a misconfigured co_manager would grant
    them the same unrestricted access as owner — the opposite of what the
    role is for. Raising instead surfaces the misconfiguration immediately.
    """
    if user.role == "co_manager":
        if not user.marca_asignada:
            raise PermissionDenied(
                "Tu cuenta de co-manager no tiene una marca asignada. Contactá a un administrador."
            )
        return user.marca_asignada
    return None


class NotReception(BasePermission):
    """Blocks the reception role outright; owner and co_manager pass through."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role != "reception")


class ReadOnlyForReception(BasePermission):
    """reception gets safe methods only (GET/HEAD/OPTIONS); owner and co_manager
    are unrestricted."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.role == "reception":
            return request.method in SAFE_METHODS
        return True
