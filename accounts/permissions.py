from rest_framework import permissions


def is_platform_admin(user) -> bool:
    """True for role=ADMIN, Django staff, or superuser."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return getattr(user, "role", "") == "ADMIN"


class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to admin users (role ADMIN, staff, or superuser).
    """
    def has_permission(self, request, view):
        return is_platform_admin(request.user)

class IsAgentUser(permissions.BasePermission):
    """
    Allows access only to agent users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'AGENT')

class IsCustomerUser(permissions.BasePermission):
    """
    Allows access only to customer users.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'CUSTOMER')
