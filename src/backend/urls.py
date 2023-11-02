"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.urls import path, include

from xterm import views as xterms_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', xterms_views.index, name='index'),

    path('images', xterms_views.images, name='images'),
    path('images/ajax', xterms_views.ajax_images, name='ajax-images'),
    path('images/remove', xterms_views.remove_image, name='remove-image'),
    path('images/run', xterms_views.run_image, name='run-image'),

    path('containers', xterms_views.containers, name='containers'),
    path('containers/ajax', xterms_views.ajax_containers, name='ajax-containers'),
    path('containers/start-stop-remove', xterms_views.start_stop_remove, name='start-stop-remove'),

    path('console/<slug:id>', xterms_views.shell_console, name='shell-console'),
    path('attach/<slug:id>', xterms_views.attach_console, name='attach-console'),

    path('browse', xterms_views.browse, name='browse'),

    path('progress/<slug:task_id>', xterms_views.check_progress, name='check-progress'),

    path('django-rq/', include('django_rq.urls'))
]

from django.conf.urls.static import static
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
