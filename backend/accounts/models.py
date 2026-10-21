from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('enseignant', 'Enseignant'),
    ]
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('valide', 'Validé'),
        ('refuse', 'Refusé'),
        ('desactive', 'Désactivé'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='enseignant')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    telephone = models.CharField(max_length=30, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.role} - {self.statut})"

    def is_admin(self):
        return self.role == 'admin'

    def is_enseignant_valide(self):
        return self.role == 'enseignant' and self.statut == 'valide'