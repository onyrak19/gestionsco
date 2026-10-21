"""
Contrôle du statut des comptes.

Un enseignant ne peut utiliser l'application que si son statut est « valide ».
Ce contrôle est appliqué à CHAQUE requête (pas seulement à la connexion) et
aussi au renouvellement du token : un compte désactivé ou refusé perd donc
l'accès immédiatement, sans attendre l'expiration de son token.
"""
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

MESSAGES_STATUT = {
    'en_attente': 'Votre compte est en attente de validation.',
    'refuse': 'Votre demande a été refusée.',
    'desactive': 'Votre compte a été désactivé.',
}
MESSAGE_SANS_PROFIL = "Votre compte n'a pas de profil. Contactez l'administrateur."


def message_blocage(user):
    """Retourne None si le compte peut se servir de l'application,
    sinon le message à afficher à l'utilisateur."""
    profile = getattr(user, 'profile', None)
    if profile is None:
        return MESSAGE_SANS_PROFIL
    if profile.role == 'enseignant' and profile.statut != 'valide':
        return MESSAGES_STATUT.get(profile.statut, "Votre compte n'est pas actif.")
    return None


class StatutJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        message = message_blocage(user)
        if message:
            raise AuthenticationFailed(message, code='compte_bloque')
        return user
