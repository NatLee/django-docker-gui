from django.urls import path

from custom_jwt import views

urlpatterns = [
    path("token", views.MyTokenObtainPairView.as_view(), name="token_get"),
    path("token/refresh", views.MyTokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify", views.MyTokenVerifyView.as_view(), name="token_verify"),
]
