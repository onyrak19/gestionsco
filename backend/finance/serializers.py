"""Validation des données reçues et mise en forme des données envoyées (finances)."""
from decimal import Decimal

from rest_framework import serializers

from school.models import AnneeScolaire, Inscription

from . import services
from .models import (
    AvanceSalaire, CategorieFinance, Employe, MODES_PAIEMENT, Mouvement, Paiement, PaieSalaire,
)

MODES = [m for m, _l in MODES_PAIEMENT]


def nom_utilisateur(u):
    return ((u.get_full_name() or u.username) if u else '')


def montant_champ(**options):
    return serializers.DecimalField(max_digits=12, decimal_places=2, **options)


# ---------------------------------------------------------------------------
# Tarifs
# ---------------------------------------------------------------------------
class AutreFraisSerializer(serializers.Serializer):
    libelle = serializers.CharField(max_length=100)
    montant = montant_champ(min_value=Decimal('0'))


class TarifNiveauSerializer(serializers.Serializer):
    annee = serializers.PrimaryKeyRelatedField(queryset=AnneeScolaire.objects.all())
    niveau = serializers.CharField(max_length=40)
    serie = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    droit_inscription = montant_champ(min_value=Decimal('0'), required=False, allow_null=True)
    ecolage_mensuel = montant_champ(min_value=Decimal('0'), required=False, allow_null=True)
    autres = AutreFraisSerializer(many=True, required=False)
    appliquer_a_toutes_series = serializers.BooleanField(required=False, default=False)

    def validate_autres(self, valeur):
        noms = [a['libelle'].strip().lower() for a in valeur]
        if any(not n for n in noms):
            raise serializers.ValidationError("Chaque frais doit avoir un libellé.")
        if len(noms) != len(set(noms)):
            raise serializers.ValidationError("Un frais est présent plusieurs fois.")
        return valeur


class TarifsCopieSerializer(serializers.Serializer):
    de = serializers.PrimaryKeyRelatedField(queryset=AnneeScolaire.objects.all())
    vers = serializers.PrimaryKeyRelatedField(queryset=AnneeScolaire.objects.all())
    ecraser = serializers.BooleanField(required=False, default=False)


# ---------------------------------------------------------------------------
# Paiements d'élèves
# ---------------------------------------------------------------------------
class PaiementEntreeSerializer(serializers.Serializer):
    inscription = serializers.PrimaryKeyRelatedField(
        queryset=Inscription.objects.select_related('eleve', 'classe', 'annee_scolaire'))
    type = serializers.ChoiceField(choices=[t for t, _l in Paiement.TYPES])
    mois = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True, allow_null=True)
    tarif = serializers.IntegerField(required=False, allow_null=True)
    date = serializers.DateField(required=False)
    mode = serializers.ChoiceField(choices=MODES, required=False, default='especes')
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    observation = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    apercu = serializers.BooleanField(required=False, default=False)

    def validate_date(self, valeur):
        if valeur > services.aujourd_hui():
            raise serializers.ValidationError("La date du paiement ne peut pas être dans le futur.")
        return valeur


class AnnulationSerializer(serializers.Serializer):
    motif = serializers.CharField(max_length=255)


def paiement_dict(p, avec_lignes=True):
    donnees = {
        'id': p.id, 'numero': p.numero, 'date': p.date.isoformat(),
        'type': p.type, 'type_libelle': p.get_type_display(),
        'mode': p.mode, 'mode_libelle': p.get_mode_display(),
        'reference': p.reference, 'observation': p.observation,
        'montant_total': services.num(p.montant_total),
        'inscription': p.inscription_id, 'annee_scolaire': p.annee_scolaire_id,
        'eleve_nom': p.eleve_nom, 'matricule': p.matricule,
        'classe_nom': p.classe_nom, 'annee_libelle': p.annee_libelle,
        'saisi_par_nom': nom_utilisateur(p.saisi_par), 'created_at': p.created_at,
        'annule': p.annule, 'motif_annulation': p.motif_annulation,
        'annule_le': p.annule_le, 'annule_par_nom': nom_utilisateur(p.annule_par),
    }
    if avec_lignes:
        donnees['lignes'] = [{
            'libelle': l.libelle, 'mois': services.mois_cle(l.mois) if l.mois else None,
            'montant': services.num(l.montant),
        } for l in p.lignes.all()]
    return donnees


# ---------------------------------------------------------------------------
# Catégories, dépenses et entrées
# ---------------------------------------------------------------------------
class CategorieSerializer(serializers.ModelSerializer):
    sens_libelle = serializers.CharField(source='get_sens_display', read_only=True)
    utilisations = serializers.SerializerMethodField()

    class Meta:
        model = CategorieFinance
        fields = ['id', 'nom', 'sens', 'sens_libelle', 'actif', 'utilisations']
        validators = []

    def get_utilisations(self, obj):
        return obj.mouvements.count()

    def validate(self, attrs):
        inst = self.instance
        nom = attrs.get('nom', inst.nom if inst else '').strip()
        sens = attrs.get('sens', inst.sens if inst else None)
        if not nom:
            raise serializers.ValidationError({'nom': "Le nom est obligatoire."})
        doublon = CategorieFinance.objects.filter(sens=sens, nom__iexact=nom)
        if inst:
            doublon = doublon.exclude(pk=inst.pk)
            if sens != inst.sens and inst.mouvements.exists():
                raise serializers.ValidationError(
                    {'sens': "Cette catégorie est déjà utilisée : on ne peut plus changer son sens."})
        if doublon.exists():
            raise serializers.ValidationError({'nom': "Cette catégorie existe déjà."})
        attrs['nom'] = nom
        return attrs


class MouvementSerializer(serializers.ModelSerializer):
    categorie_nom = serializers.CharField(source='categorie.nom', read_only=True)
    sens = serializers.CharField(read_only=True)
    sens_libelle = serializers.CharField(source='categorie.get_sens_display', read_only=True)
    saisi_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = Mouvement
        fields = ['id', 'date', 'categorie', 'categorie_nom', 'sens', 'sens_libelle', 'libelle', 'montant',
                  'imprevu', 'reference', 'notes', 'saisi_par_nom', 'created_at']
        read_only_fields = ['created_at']

    def get_saisi_par_nom(self, obj):
        return nom_utilisateur(obj.saisi_par)

    def validate_montant(self, valeur):
        if valeur <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
        return valeur

    def validate_libelle(self, valeur):
        if not valeur.strip():
            raise serializers.ValidationError("Le libellé est obligatoire.")
        return valeur.strip()

    def validate_categorie(self, categorie):
        ancienne = self.instance.categorie_id if self.instance else None
        if not categorie.actif and categorie.id != ancienne:
            raise serializers.ValidationError("Cette catégorie est désactivée.")
        return categorie

    def create(self, validated_data):
        utilisateur = getattr(self.context.get('request'), 'user', None)
        if getattr(utilisateur, 'pk', None):
            validated_data['saisi_par'] = utilisateur
        return super().create(validated_data)


# ---------------------------------------------------------------------------
# Employés, avances, salaires
# ---------------------------------------------------------------------------
class EmployeSerializer(serializers.ModelSerializer):
    nom_complet = serializers.ReadOnlyField()
    avances_dues = serializers.SerializerMethodField()

    class Meta:
        model = Employe
        fields = ['id', 'nom', 'prenom', 'nom_complet', 'poste', 'telephone', 'salaire_mensuel',
                  'date_embauche', 'actif', 'user', 'avances_dues']

    def get_avances_dues(self, obj):
        return services.num(services.total_avances_en_cours(obj))

    def validate_nom(self, valeur):
        if not valeur.strip():
            raise serializers.ValidationError("Le nom est obligatoire.")
        return valeur.strip()

    def validate_salaire_mensuel(self, valeur):
        if valeur < 0:
            raise serializers.ValidationError("Le salaire ne peut pas être négatif.")
        return valeur


class AvanceSerializer(serializers.ModelSerializer):
    employe_nom = serializers.CharField(source='employe.nom_complet', read_only=True)
    restant = serializers.SerializerMethodField()
    saisi_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = AvanceSalaire
        fields = ['id', 'employe', 'employe_nom', 'date', 'montant', 'motif', 'annulee', 'restant',
                  'saisi_par_nom', 'created_at']
        read_only_fields = ['annulee', 'created_at']

    def get_restant(self, obj):
        if obj.annulee:
            return 0.0
        retenu = sum((r.montant for r in obj.retenues.all() if not r.paie.annule), Decimal('0'))
        return services.num(obj.montant - retenu)

    def get_saisi_par_nom(self, obj):
        return nom_utilisateur(obj.saisi_par)

    def validate_montant(self, valeur):
        if valeur <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
        return valeur

    def validate_date(self, valeur):
        if valeur > services.aujourd_hui():
            raise serializers.ValidationError("La date ne peut pas être dans le futur.")
        return valeur

    def validate_employe(self, employe):
        if not employe.actif:
            raise serializers.ValidationError("Cet employé n'est plus actif.")
        return employe

    def create(self, validated_data):
        utilisateur = getattr(self.context.get('request'), 'user', None)
        if getattr(utilisateur, 'pk', None):
            validated_data['saisi_par'] = utilisateur
        return super().create(validated_data)


class SalaireEntreeSerializer(serializers.Serializer):
    employe = serializers.PrimaryKeyRelatedField(queryset=Employe.objects.all())
    mois = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True, allow_null=True)
    exceptionnel = serializers.BooleanField(required=False, default=False)
    montant_exceptionnel = montant_champ(required=False, allow_null=True)
    motif_exceptionnel = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    retenue_avance = montant_champ(required=False, allow_null=True)
    autres_retenues = montant_champ(required=False, allow_null=True, default=Decimal('0'))
    motif_retenues = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    date = serializers.DateField(required=False)
    mode = serializers.ChoiceField(choices=MODES, required=False, default='especes')
    observation = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    apercu = serializers.BooleanField(required=False, default=False)

    def validate_date(self, valeur):
        if valeur > services.aujourd_hui():
            raise serializers.ValidationError("La date du paiement ne peut pas être dans le futur.")
        return valeur


class SalaireGroupeSerializer(serializers.Serializer):
    employes = serializers.JSONField()          # liste d'identifiants ou "tous"
    mois = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    date = serializers.DateField(required=False)
    mode = serializers.ChoiceField(choices=MODES, required=False, default='especes')
    # retenues supplémentaires par employé : {"12": {"montant": 5000, "motif": "Pénalité"}}
    retenues = serializers.DictField(child=serializers.DictField(), required=False)
    apercu = serializers.BooleanField(required=False, default=False)

    def validate_employes(self, valeur):
        if valeur == 'tous':
            return valeur
        if not isinstance(valeur, list) or not valeur:
            raise serializers.ValidationError("Choisissez des employés (liste d'identifiants, ou « tous »).")
        try:
            return [int(v) for v in valeur]
        except (TypeError, ValueError):
            raise serializers.ValidationError("Identifiants d'employés invalides.")

    def validate_date(self, valeur):
        if valeur > services.aujourd_hui():
            raise serializers.ValidationError("La date du paiement ne peut pas être dans le futur.")
        return valeur


def paie_dict(p, avec_lignes=True):
    donnees = {
        'id': p.id, 'numero': p.numero, 'date': p.date.isoformat(),
        'employe': p.employe_id, 'employe_nom': p.employe_nom, 'poste': p.poste,
        'mode': p.mode, 'mode_libelle': p.get_mode_display(),
        'salaire_mensuel': services.num(p.salaire_mensuel),
        'montant_brut': services.num(p.montant_brut),
        'retenue_avances': services.num(p.retenue_avances),
        'autres_retenues': services.num(p.autres_retenues), 'motif_retenues': p.motif_retenues,
        'net_paye': services.num(p.net_paye),
        'exceptionnel': p.exceptionnel, 'motif_exceptionnel': p.motif_exceptionnel,
        'observation': p.observation, 'saisi_par_nom': nom_utilisateur(p.saisi_par),
        'created_at': p.created_at,
        'annule': p.annule, 'motif_annulation': p.motif_annulation, 'annule_le': p.annule_le,
    }
    if avec_lignes:
        donnees['mois'] = [{'mois': services.mois_cle(l.mois), 'libelle': services.libelle_mois(l.mois)}
                           for l in p.lignes.all()]
        donnees['retenues'] = [{'avance': r.avance_id, 'montant': services.num(r.montant)}
                               for r in p.retenues.all()]
    return donnees
