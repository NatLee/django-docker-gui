import logging

from django.conf import settings
from django.contrib.auth.models import User
from google.auth.transport import requests
from google.oauth2 import id_token
from rest_framework import serializers

from custom_auth.exception import InvalidEmailError
from custom_auth.models import SocialAccount

logger = logging.getLogger(__name__)


def email_may_register(email: str) -> bool:
    """Only addresses on a domain listed in settings.VALID_REGISTER_DOMAINS may sign up."""
    domain = email.rpartition("@")[2].lower()
    return domain in {d.lower() for d in settings.VALID_REGISTER_DOMAINS}


class SocialLoginSerializer(serializers.Serializer):
    # Google login
    credential = serializers.CharField(required=True)

    def verify_token(self, credential):
        """The claims of a Google ID token issued for our client ID. google-auth checks the
        signature, expiry, issuer and audience; it raises ValueError or GoogleAuthError otherwise."""
        logger.debug("Verifying a Google ID token")
        return id_token.verify_oauth2_token(credential, requests.Request(), settings.SOCIAL_GOOGLE_CLIENT_ID)

    def create(self, validated_data):
        idinfo = self.verify_token(validated_data.get("credential"))
        social = SocialAccount.objects.filter(unique_id=idinfo["sub"]).select_related("user").first()
        if social:
            return social.user

        email = idinfo.get("email", "")
        if not idinfo.get("email_verified") or not email_may_register(email):
            logger.warning("`%s` attempted to register", email)
            raise InvalidEmailError
        user = User.objects.create_user(
            username=email.split("@")[0],
            first_name=idinfo.get("given_name", ""),
            last_name=idinfo.get("family_name", ""),
            email=email,
        )
        logger.info("Created user [%s] - [%s]", user.username, email)
        SocialAccount.objects.create(user=user, unique_id=idinfo["sub"])
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name"]
