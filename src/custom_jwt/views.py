from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

# The pages read "access_token" and "refresh_token" instead of SimpleJWT's "access" / "refresh".


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        return {"refresh_token": data["refresh"], "access_token": data["access"]}


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer


class MyTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        return {"access_token": data["access"]}


class MyTokenRefreshView(TokenRefreshView):
    serializer_class = MyTokenRefreshSerializer
