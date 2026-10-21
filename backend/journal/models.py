from django.conf import settings
from django.db import models


class Activite(models.Model):
    """Une ligne du journal : qui a fait quoi, quand.

    Le journal est en ajout seulement : l'application n'offre aucun moyen de
    modifier ou de supprimer une ligne. Les noms (utilisateur, élève, classe...)
    sont recopiés en texte pour rester lisibles même si l'objet est supprimé
    plus tard.
    """
    CATEGORIES = [
        ('connexion', 'Connexions'),
        ('note', 'Notes'),
        ('inscription', 'Inscriptions'),
        ('piece_jointe', 'Pièces jointes'),
        ('eleve', 'Élèves'),
        ('classe', 'Classes'),
        ('matiere', 'Matières'),
        ('affectation', 'Affectations'),
        ('annee', 'Années scolaires'),
        ('enseignant', 'Enseignants'),
        ('impression', 'Impressions'),
        ('etablissement', 'Établissement'),
        ('export', 'Exports Excel'),
        ('import', 'Imports Excel'),
        ('paiement', 'Paiements des élèves'),
        ('finance', 'Finances (dépenses, entrées, tarifs)'),
        ('salaire', 'Salaires et avances'),
    ]
    ACTIONS = [
        ('creation', 'Création'),
        ('modification', 'Modification'),
        ('suppression', 'Suppression'),
        ('connexion', 'Connexion'),
        ('echec', 'Échec'),
        ('impression', 'Impression'),
        ('cloture', 'Clôture'),
        ('validation', 'Validation'),
    ]

    date = models.DateTimeField(auto_now_add=True, db_index=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    utilisateur_nom = models.CharField(max_length=150, blank=True)
    utilisateur_role = models.CharField(max_length=20, blank=True)
    categorie = models.CharField(max_length=20, choices=CATEGORIES, db_index=True)
    action = models.CharField(max_length=20, choices=ACTIONS, db_index=True)
    description = models.TextField()
    annee = models.CharField(max_length=20, blank=True, default='', db_index=True)
    classe = models.CharField(max_length=60, blank=True, default='')
    matiere = models.CharField(max_length=100, blank=True, default='')
    eleve = models.CharField(max_length=220, blank=True, default='')
    cible_id = models.PositiveBigIntegerField(null=True, blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = 'activité'
        verbose_name_plural = 'activités'

    def __str__(self):
        return f"{self.date:%d/%m/%Y %H:%M} — {self.description[:80]}"
