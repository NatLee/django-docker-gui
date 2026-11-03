from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
    TokenVerifySerializer,
)
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

from backend.access import LOGIN_REFUSED, SUPERUSERS_ONLY, may_use_app

# The pages read "access_token" and "refresh_token" instead of SimpleJWT's "access" / "refresh".
# Who gets a token at all is SIMPLE_JWT["USER_AUTHENTICATION_RULE"] (backend/access.py).


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    default_error_messages = {"no_active_account": LOGIN_REFUSED}

    def validate(self, attrs):
        data = super().validate(attrs)
        return {"refresh_token": data["refresh"], "access_token": data["access"]}


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class MyTokenRefreshSerializer(TokenRefreshSerializer):
    default_error_messages = {"no_active_account": SUPERUSERS_ONLY}

    def validate(self, attrs):
        data = super().validate(attrs)
        return {"access_token": data["access"]}


class MyTokenRefreshView(TokenRefreshView):
    serializer_class = MyTokenRefreshSerializer


class MyTokenVerifySerializer(TokenVerifySerializer):
    """Every page asks this on load. Besides the signature and expiry, the token's user must still
    pass the access rule, so an account that lost superuser is sent back to the login page."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user = JWTAuthentication().get_user(UntypedToken(attrs["token"]))
        if not may_use_app(user):
            raise AuthenticationFailed({"detail": SUPERUSERS_ONLY, "code": "superusers_only"})
        return data


class MyTokenVerifyView(TokenVerifyView):
    serializer_class = MyTokenVerifySerializer
