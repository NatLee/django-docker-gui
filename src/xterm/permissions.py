"""Who may do what. Every API view and WebSocket consumer asks these functions, nothing else.

There is no per-container ownership: whoever may manage Docker may act on every container,
including the one this app runs in. Since the app holds the Docker socket, that already amounts
to root on the host, so treat every account as an administrator.
"""
from rest_framework.permissions import BasePermission


def can_manage_docker(user) -> bool:
    """List, start, stop, restart and remove containers and images, pull images, open a console
    or attach to a container: any active, logged-in account."""
    return bool(user is not None and user.is_authenticated and user.is_active)


def can_open_host_shell(user) -> bool:
    """The Terminal page, a shell inside this app's own container: superusers only."""
    return can_manage_docker(user) and user.is_superuser


class CanManageDocker(BasePermission):
    """DRF permission for the Docker API views."""

    def has_permission(self, request, view) -> bool:
        return can_manage_docker(request.user)
