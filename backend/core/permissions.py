from rest_framework.permissions import BasePermission


class IsStaffUser(BasePermission):
    """Enforced server-side for every admin endpoint; hiding links in the UI is not security."""
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.is_staff)
