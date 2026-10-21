"""Supprime du disque les fichiers d'un élève ou d'une pièce jointe supprimés."""
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Eleve, PieceJointe


def _supprimer(champ_fichier):
    if champ_fichier:
        try:
            champ_fichier.storage.delete(champ_fichier.name)
        except Exception:   # noqa: BLE001 - un fichier déjà absent ne doit rien bloquer
            pass


@receiver(post_delete, sender=Eleve)
def supprimer_photo_eleve(sender, instance, **kwargs):
    _supprimer(instance.photo)


@receiver(post_delete, sender=PieceJointe)
def supprimer_fichier_piece(sender, instance, **kwargs):
    _supprimer(instance.fichier)
