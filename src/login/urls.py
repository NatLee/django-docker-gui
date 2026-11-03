from django.urls import path

from login import views

urlpatterns = [
    path('', views.Login.as_view(), name='login-page'),
]
