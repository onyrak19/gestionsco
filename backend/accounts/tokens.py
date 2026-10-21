"""Renouvellement du token d'accès : refuse les comptes qui ne sont plus
« valides » (module séparé de authentication.py pour éviter un import
circulaire avec la configuration de Django REST framework)."""
from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .authentication import message_blocage


class StatutTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        try:
            refresh = RefreshToken(attrs['refresh'])
        except TokenError as exc:
            raise AuthenticationFailed(str(exc.args[0]), code='token_not_valid')

        user = User.objects.filter(
            **{api_settings.USER_ID_FIELD: refresh.get(api_settings.USER_ID_CLAIM)}
        ).select_related('profile').first()
        if user is None or not user.is_active:
            raise AuthenticationFailed('Utilisateur introuvable ou inactif.',
                                       code='user_inactive')
        message = message_blocage(user)
        if message:
            raise AuthenticationFailed(message, code='compte_bloque')
        return super().validate(attrs)


class StatutTokenRefreshView(TokenRefreshView):
    serializer_class = StatutTokenRefreshSerializer
