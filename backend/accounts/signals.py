from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=User)
def profil_admin_pour_superuser(sender, instance, **kwargs):
    """Un superuser (créé avec `manage.py createsuperuser`) reçoit
    automatiquement un profil administrateur validé. Sans cela, il ne pourrait
    pas se connecter à l'application."""
    if instance.is_superuser and not UserProfile.objects.filter(user=instance).exists():
        UserProfile.objects.create(user=instance, role='admin', statut='valide')
