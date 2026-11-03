import logging

from django.conf import settings
from django.contrib.auth import login
from google.auth.exceptions import GoogleAuthError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from custom_auth.exception import InvalidEmailError
from custom_auth.serializers import SocialLoginSerializer
from custom_jwt.views import MyTokenObtainPairView

logger = logging.getLogger(__name__)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token),
    }


class GoogleLogin(MyTokenObtainPairView):
    """Trade a Google ID token for this app's tokens. Off unless GOOGLE_CLIENT_ID is set."""

    permission_classes = (AllowAny,)  # AllowAny for login
    serializer_class = SocialLoginSerializer

    def post(self, request):
        if not settings.SOCIAL_GOOGLE_CLIENT_ID:
            return Response({"status": "error", "detail": "Google sign-in is not enabled."}, status=404)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except InvalidEmailError:
            return Response({"status": "error", "detail": "This email is invalid."}, status=401)
        except (ValueError, GoogleAuthError) as e:
            logger.warning("Google sign-in refused: %s", e)
            return Response({"status": "error", "detail": "The Google credential is invalid."}, status=401)
        login(request=request, user=user)
        return Response(get_tokens_for_user(user))
