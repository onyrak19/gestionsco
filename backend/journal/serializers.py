from rest_framework import serializers

from .models import Activite


class ActiviteSerializer(serializers.ModelSerializer):
    categorie_libelle = serializers.CharField(source='get_categorie_display', read_only=True)
    action_libelle = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = Activite
        fields = ['id', 'date', 'utilisateur', 'utilisateur_nom', 'utilisateur_role',
                  'categorie', 'categorie_libelle', 'action', 'action_libelle',
                  'description', 'annee', 'classe', 'matiere', 'eleve', 'adresse_ip']
        read_only_fields = fields
