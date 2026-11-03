"""URLs: the pages and API of xterm, logins (JWT and optional Google), and the admin pages:
Django admin, the RQ dashboard and the API docs (Swagger / ReDoc, staff only)."""
from django.contrib import admin
from django.urls import include, path, re_path
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view
from rest_framework.permissions import IsAdminUser

URL_PREFIX = 'api'

urlpatterns = [
    path(f"{URL_PREFIX}/__hidden_admin/", admin.site.urls),
    path(f'{URL_PREFIX}/__django-rq/', include('django_rq.urls')),
    path(f"{URL_PREFIX}/auth/google/", include("custom_auth.urls")),
    path(f"{URL_PREFIX}/auth/", include("custom_jwt.urls")),
    path("login", include("login.urls"), name="login"),
    path("", include("xterm.urls"), name="xterm"),
]


class BothHttpAndHttpsSchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request, public)
        schema.schemes = ["http", "https"]
        return schema


schema_view = get_schema_view(
    openapi.Info(
        title="Backend service API",
        default_version="v1",
        description="API of backend services.",
    ),
    public=True,
    permission_classes=(IsAdminUser,),  # staff only
    generator_class=BothHttpAndHttpsSchemaGenerator,
)

urlpatterns += [
    re_path(rf"^{URL_PREFIX}/__hidden_swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    re_path(rf"^{URL_PREFIX}/__hidden_swagger", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    re_path(rf"^{URL_PREFIX}/__hidden_redoc", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
