"""Crée (ou répare) le compte administrateur à partir de variables d'environnement.

Utile sur l'offre gratuite de Render, où l'on n'a pas de terminal pour lancer
« createsuperuser ». Lancé automatiquement à chaque démarrage ; sans effet si
le compte existe déjà.

Variables :
  ADMIN_USERNAME        nom d'utilisateur (défaut : admin)
  ADMIN_PASSWORD        mot de passe (obligatoire, 8 caractères minimum)
  ADMIN_EMAIL           adresse e-mail (facultatif)
  ADMIN_RESET_PASSWORD  « True » : remplace le mot de passe d'un compte existant
                        (mot de passe oublié). À remettre à False ensuite.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserProfile


def _vrai(valeur):
    return (valeur or '').strip().lower() in ('1', 'true', 'yes', 'on')


class Command(BaseCommand):
    help = "Crée le compte administrateur depuis ADMIN_USERNAME / ADMIN_PASSWORD."

    def handle(self, *args, **options):
        username = (os.environ.get('ADMIN_USERNAME') or 'admin').strip()
        password = os.environ.get('ADMIN_PASSWORD') or ''
        email = (os.environ.get('ADMIN_EMAIL') or '').strip()
        reinitialiser = _vrai(os.environ.get('ADMIN_RESET_PASSWORD'))

        if not password:
            self.stdout.write(self.style.WARNING(
                "ADMIN_PASSWORD n'est pas défini : aucun compte administrateur créé."))
            return
        if len(password) < 8:
            self.stdout.write(self.style.WARNING(
                "ADMIN_PASSWORD fait moins de 8 caractères : compte administrateur non créé."))
            return

        User = get_user_model()
        user = User.objects.filter(username=username).first()

        if user is None:
            user = User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Compte administrateur « {username} » créé."))
        elif not user.is_superuser:
            self.stdout.write(self.style.WARNING(
                f"« {username} » existe déjà mais n'est pas administrateur : "
                "choisissez un autre ADMIN_USERNAME."))
            return
        elif reinitialiser:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Mot de passe de « {username} » réinitialisé "
                "(remettez ADMIN_RESET_PASSWORD à False)."))
        else:
            self.stdout.write(f"Compte administrateur « {username} » déjà présent : rien à faire.")

        # Le profil « admin validé » est nécessaire pour se connecter à l'application
        UserProfile.objects.update_or_create(
            user=user, defaults={'role': 'admin', 'statut': 'valide'})
