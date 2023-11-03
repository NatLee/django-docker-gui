from django.urls import path
import logging

from xterm import views

logger = logging.getLogger(__name__)

urlpatterns = [
    path('', views.index, name='index'),

    path('images', views.images, name='images'),
    path('api/images', views.ImagesListView.as_view(), name='images-api'),
    path('api/images/remove', views.remove_image, name='remove-image'),
    path('api/images/run', views.run_image, name='run-image'),

    path('containers', views.containers, name='containers'),
    path('api/containers', views.ContainersListView.as_view(), name='containers-api'),
    path('api/containers/start-stop-remove', views.start_stop_remove, name='start-stop-remove'),

    path('api/console/<str:action>/<str:id>', views.ConsoleView.as_view(), name='console'),

    path('console/shell/<slug:id>', views.console, name='shell-console'),
    path('console/attach/<slug:id>', views.console, name='attach-console'),

    path('browse', views.browse, name='browse'),

    path('progress/<slug:task_id>', views.check_progress, name='check-progress'),

]