"""Who may use this app: active superusers, and nobody else.

The app holds the host's Docker socket, and a console in its own container reaches that socket, so
any account that can use the app can take over the host. That is why there is one rule for the
whole app instead of finer roles (the owner's decision, 2026-11-04). Setups with several users
belong in dev-dock-manager, which gives each person their own desktop container.

The rule is wired in once per entry point, never per view:
- logging in and refreshing tokens: SIMPLE_JWT["USER_AUTHENTICATION_RULE"]
- the REST API (and the API docs): REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]
- the WebSockets: xterm.consumers.AuthenticatedConsumer
- Django admin and the RQ pages: SuperuserAdminSite, the project's default admin site
"""
from django.contrib import admin
from django.contrib.admin.apps import AdminConfig
from rest_framework.permissions import BasePermission

SUPERUSERS_ONLY = (
    "This app is for superusers only: it controls the host's Docker, so any account could take "
    "over the host. Log in with a superuser account."
)
# What the login answers for a wrong password and for a non-superuser alike, so it doesn't tell
# anyone that a password was right.
LOGIN_REFUSED = "No active superuser account found with the given credentials. " + SUPERUSERS_ONLY


def may_use_app(user) -> bool:
    """The rule: an active, logged-in superuser."""
    return bool(user is not None and user.is_authenticated and user.is_active and user.is_superuser)


class SuperusersOnly(BasePermission):
    """The rule for DRF; the default permission class of every API view."""

    message = SUPERUSERS_ONLY

    def has_permission(self, request, view) -> bool:
        return may_use_app(request.user)


class SuperuserAdminSite(admin.AdminSite):
    """Django admin (and the RQ pages wrapped in it) for superusers only, not every staff account."""

    def has_permission(self, request) -> bool:
        return may_use_app(request.user)


class SuperuserAdminConfig(AdminConfig):
    """Makes SuperuserAdminSite the default `admin.site` (Django's documented way to swap it)."""

    default_site = "backend.access.SuperuserAdminSite"
