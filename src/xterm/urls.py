from django.urls import path

from xterm import views

urlpatterns = [
    path('', views.Index.as_view(), name='index'),

    path('images', views.Page.as_view(template_name='images.html'), name='images'),
    path('api/images', views.ImagesListView.as_view(), name='images-api'),
    path('api/images/remove', views.remove_image, name='remove-image'),
    path('api/images/run', views.run_image, name='run-image'),

    path('containers', views.Page.as_view(template_name='containers.html'), name='containers'),
    path('api/containers', views.ContainersListView.as_view(), name='containers-api'),
    path('api/containers/start-stop-remove', views.start_stop_remove, name='start-stop-remove'),

    path('api/console/<str:action>/<str:id>', views.ConsoleView.as_view(), name='console'),

    path('console/shell/<slug:id>', views.Page.as_view(template_name='console.html'), name='shell-console'),
    path('console/attach/<slug:id>', views.Page.as_view(template_name='console.html'), name='attach-console'),

    path('terminal', views.Page.as_view(template_name='terminal.html'), name='terminal'),

    path('browse', views.Page.as_view(template_name='browse.html'), name='browse'),
    path('api/browse', views.BrowseDockerHubView.as_view(), name='browse-api'),
]
