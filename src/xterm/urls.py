from django.urls import path
import logging

from xterm import views

logger = logging.getLogger(__name__)

urlpatterns = [
    path('', views.index, name='index'),

    path('images', views.images, name='images'),
    path('images/ajax', views.ajax_images, name='ajax-images'),
    path('images/remove', views.remove_image, name='remove-image'),
    path('images/run', views.run_image, name='run-image'),

    path('containers', views.containers, name='containers'),
    path('containers/ajax', views.ajax_containers, name='ajax-containers'),
    path('containers/start-stop-remove', views.start_stop_remove, name='start-stop-remove'),

    path('console/<slug:id>', views.shell_console, name='shell-console'),
    path('attach/<slug:id>', views.attach_console, name='attach-console'),

    path('browse', views.browse, name='browse'),

    path('progress/<slug:task_id>', views.check_progress, name='check-progress'),

]