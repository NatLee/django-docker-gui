"""URLs: the pages and API of xterm, the JWT login, and the admin pages: Django admin, the RQ
dashboard and the API docs (Swagger / ReDoc). All of it is for superusers only (backend/access.py)."""
from django.contrib import admin
from django.urls import include, path, re_path
from django_rq.urls import get_admin_urlpatterns, get_api_urlpatterns
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view

URL_PREFIX = 'api'

urlpatterns = [
    path(f"{URL_PREFIX}/__hidden_admin/", admin.site.urls),
    # The RQ pages, behind the admin login (superusers only, like the admin). The two JSON views
    # (stats.json, metrics) keep django-rq's own check: staff, or RQ_API_TOKEN, which isn't set.
    path(f'{URL_PREFIX}/__django-rq/', include((
        get_api_urlpatterns() + get_admin_urlpatterns(view_wrapper=admin.site.admin_view), "django_rq",
    ))),
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
    public=True,  # who may see it is the API's default permission: superusers only
    generator_class=BothHttpAndHttpsSchemaGenerator,
)

urlpatterns += [
    re_path(rf"^{URL_PREFIX}/__hidden_swagger(?P<format>\.json|\.yaml)$", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    re_path(rf"^{URL_PREFIX}/__hidden_swagger", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    re_path(rf"^{URL_PREFIX}/__hidden_redoc", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
