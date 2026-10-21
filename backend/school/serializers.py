import os
import re

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import QueryDict
from rest_framework import serializers

from .calculs import ConfigResolver
from .fichiers import NB_MAX_PIECES, traiter_photo, valider_piece
from .models import (
    AnneeScolaire, Classe, Matiere, Eleve, Etablissement,
    Inscription, Affectation, Note, PieceJointe, NOTE_MAX, NOTE_MIN,
)
from .niveaux import NIVEAUX_AVEC_SERIE, construire_nom_classe
from .permissions import user_is_admin
from .regles import verifier_admissibilite


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
class BlankToNullMixin:
    """Les formulaires envoient '' pour un champ laissé vide. Pour les champs
    listés dans `blank_to_null`, on le convertit en None."""
    blank_to_null = ()

    def to_internal_value(self, data):
        if any(data.get(champ) == '' for champ in self.blank_to_null):
            # QueryDict.copy() copie aussi les fichiers envoyés (impossible pour
            # les gros fichiers) : on passe par un simple dictionnaire.
            data = data.dict() if isinstance(data, QueryDict) else dict(data)
            for champ in self.blank_to_null:
                if data.get(champ) == '':
                    data[champ] = None
        return super().to_internal_value(data)


def verifier_annee_ouverte(annee):
    if annee is not None and annee.cloturee:
        raise serializers.ValidationError(
            f"L'année scolaire {annee.libelle} est clôturée : elle ne peut plus être modifiée."
        )


def verifier_matiere_enseignee(matiere, classe):
    """Si le niveau de la classe est configuré, la matière doit en faire partie."""
    if ConfigResolver().coefficient(matiere, classe) is None:
        raise serializers.ValidationError({
            'matiere': f"{matiere.nom} n'est pas enseignée en {classe.nom} : ajoutez-la "
                       f"à la configuration (matières et coefficients) de cette classe."
        })


# ---------------------------------------------------------------------------
# Établissement / année / classe / matière / élève
# ---------------------------------------------------------------------------
class EtablissementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Etablissement
        fields = ['nom', 'adresse', 'ville', 'telephone', 'email', 'directeur']


class AnneeScolaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnneeScolaire
        fields = ['id', 'libelle', 'date_debut', 'date_fin', 'active', 'cloturee']
        # La clôture passe uniquement par /annees/<id>/cloturer/ (mot de passe admin)
        read_only_fields = ['cloturee']

    def validate(self, attrs):
        inst = self.instance
        debut = attrs.get('date_debut', getattr(inst, 'date_debut', None))
        fin = attrs.get('date_fin', getattr(inst, 'date_fin', None))
        if debut and fin and fin <= debut:
            raise serializers.ValidationError(
                {'date_fin': 'La date de fin doit être postérieure à la date de début.'}
            )
        if attrs.get('active') and getattr(inst, 'cloturee', False):
            raise serializers.ValidationError("Une année clôturée ne peut pas être activée.")
        return attrs


class ClasseSerializer(serializers.ModelSerializer):
    annee_scolaire_libelle = serializers.CharField(source='annee_scolaire.libelle', read_only=True)
    nom = serializers.CharField(required=False, max_length=50)
    niveau = serializers.CharField(required=False, allow_blank=True, max_length=40)
    serie = serializers.CharField(required=False, allow_blank=True, max_length=20)
    numero = serializers.IntegerField(required=False, min_value=1, max_value=99)
    effectif = serializers.IntegerField(source='nb_eleves', read_only=True)
    configuree = serializers.SerializerMethodField()

    class Meta:
        model = Classe
        fields = ['id', 'nom', 'niveau', 'serie', 'numero', 'annee_scolaire',
                  'annee_scolaire_libelle', 'effectif', 'configuree']
        validators = []   # unicité (nom, année) contrôlée dans validate()

    def get_configuree(self, obj):
        resolver = self.context.get('resolver')
        return None if resolver is None else resolver.config(obj) is not None

    def validate_annee_scolaire(self, annee):
        if self.instance is None or self.instance.annee_scolaire_id != annee.id:
            verifier_annee_ouverte(annee)
        return annee

    def validate(self, attrs):
        inst = self.instance
        niveau = attrs.get('niveau', inst.niveau if inst else '').strip()
        serie = attrs.get('serie', inst.serie if inst else '').strip().upper()
        numero = attrs.get('numero', inst.numero if inst else 1)
        annee = attrs.get('annee_scolaire', inst.annee_scolaire if inst else None)
        nom = attrs.get('nom', inst.nom if inst else '').strip()

        if niveau:
            if niveau in NIVEAUX_AVEC_SERIE:
                if not serie:
                    raise serializers.ValidationError(
                        {'serie': 'La série est obligatoire pour ce niveau (ex. L, S, OSE).'})
            else:
                serie = ''
            nom = construire_nom_classe(niveau, serie, numero)
        else:
            serie = ''
            if not nom:
                raise serializers.ValidationError(
                    {'niveau': 'Choisissez ou saisissez le niveau de la classe.'})

        doublon = Classe.objects.filter(nom=nom, annee_scolaire=annee)
        if inst:
            doublon = doublon.exclude(pk=inst.pk)
        if doublon.exists():
            raise serializers.ValidationError(
                {'numero': f"La classe « {nom} » existe déjà pour cette année."})

        attrs.update(niveau=niveau, serie=serie, numero=numero, nom=nom)
        return attrs


class MatiereSerializer(serializers.ModelSerializer):
    """Le code est attribué automatiquement (MAT, FRA, ...)."""
    class Meta:
        model = Matiere
        fields = ['id', 'nom', 'code', 'coefficient']
        read_only_fields = ['code']


class EleveSerializer(BlankToNullMixin, serializers.ModelSerializer):
    """Le matricule est attribué automatiquement à la première inscription."""
    blank_to_null = ('date_naissance',)
    # Photo facultative : envoyée en multipart, réduite et convertie en JPEG
    photo = serializers.FileField(write_only=True, required=False)
    retirer_photo = serializers.BooleanField(write_only=True, required=False, default=False)
    a_photo = serializers.SerializerMethodField()
    photo_token = serializers.ReadOnlyField()
    derniere_classe = serializers.SerializerMethodField()
    derniere_annee = serializers.SerializerMethodField()
    derniere_decision = serializers.SerializerMethodField()

    class Meta:
        model = Eleve
        fields = ['id', 'matricule', 'nom', 'prenom', 'date_naissance', 'sexe', 'actif',
                  'parent_nom', 'parent_mobile', 'parent2_nom', 'parent2_mobile',
                  'photo', 'retirer_photo', 'a_photo', 'photo_token',
                  'derniere_classe', 'derniere_annee', 'derniere_decision']
        read_only_fields = ['matricule']

    def get_a_photo(self, obj):
        return bool(obj.photo)

    @staticmethod
    def _mobile_valide(valeur):
        valeur = (valeur or '').strip()
        if valeur and not re.fullmatch(r'\+?[0-9][0-9 .()\-]{3,28}', valeur):
            raise serializers.ValidationError(
                "Numéro de mobile invalide (chiffres, espaces, +, -, . et parenthèses seulement).")
        return valeur

    def validate_parent_mobile(self, valeur):
        return self._mobile_valide(valeur)

    def validate_parent2_mobile(self, valeur):
        return self._mobile_valide(valeur)

    def validate_photo(self, fichier):
        try:
            octets = traiter_photo(fichier)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return ContentFile(octets, name='photo.jpg')

    def create(self, validated_data):
        validated_data.pop('retirer_photo', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        retirer = validated_data.pop('retirer_photo', False)
        if retirer and 'photo' not in validated_data:
            validated_data['photo'] = ''
        ancienne = instance.photo.name if instance.photo else ''
        instance = super().update(instance, validated_data)
        nouvelle = instance.photo.name if instance.photo else ''
        if ancienne and ancienne != nouvelle:   # l'ancienne photo ne sert plus
            try:
                instance.photo.storage.delete(ancienne)
            except Exception:   # noqa: BLE001
                pass
        return instance

    def _derniere(self, obj):
        liste = getattr(obj, 'insc_all', None)   # chargé par la vue liste
        return liste[0] if liste else None

    def get_derniere_classe(self, obj):
        d = self._derniere(obj)
        return d.classe.nom if d else None

    def get_derniere_annee(self, obj):
        d = self._derniere(obj)
        return d.annee_scolaire.libelle if d else None

    def get_derniere_decision(self, obj):
        d = self._derniere(obj)
        return d.decision if d else None


# ---------------------------------------------------------------------------
# Inscription / affectation
# ---------------------------------------------------------------------------
class PieceJointeSerializer(serializers.ModelSerializer):
    ajoute_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = PieceJointe
        fields = ['id', 'inscription', 'libelle', 'nom_original', 'taille', 'type_mime',
                  'date_ajout', 'ajoute_par_nom']
        read_only_fields = fields

    def get_ajoute_par_nom(self, obj):
        u = obj.ajoute_par
        return (u.get_full_name() or u.username) if u else ''


def lire_pieces_envoyees(request):
    """Pièces jointes d'un envoi multipart : champ « fichiers » (un ou plusieurs)
    et champ « libelles » (un libellé par fichier, dans le même ordre).
    Toutes sont facultatives. Retourne [(fichier, libellé, type MIME)]."""
    if request is None:
        return []
    fichiers = request.FILES.getlist('fichiers')
    if not fichiers:
        return []
    if len(fichiers) > NB_MAX_PIECES:
        raise serializers.ValidationError(
            {'fichiers': f"Maximum {NB_MAX_PIECES} fichiers à la fois."})
    libelles = request.data.getlist('libelles') if hasattr(request.data, 'getlist') else []
    pieces = []
    for i, fichier in enumerate(fichiers):
        debut = fichier.read(16)
        fichier.seek(0)
        try:
            _extension, type_mime = valider_piece(fichier.name, debut, fichier.size)
        except ValueError as exc:
            raise serializers.ValidationError({'fichiers': str(exc)})
        libelle = (libelles[i] if i < len(libelles) else '').strip()[:120]
        pieces.append((fichier, libelle, type_mime))
    return pieces


def creer_pieces(inscription, pieces, auteur):
    """Enregistre les pièces validées par `lire_pieces_envoyees`."""
    auteur = auteur if getattr(auteur, 'pk', None) else None
    return [
        PieceJointe.objects.create(
            inscription=inscription, fichier=fichier, libelle=libelle,
            nom_original=os.path.basename(fichier.name)[:255], taille=fichier.size,
            type_mime=type_mime, ajoute_par=auteur,
        )
        for fichier, libelle, type_mime in pieces
    ]


class InscriptionSerializer(serializers.ModelSerializer):
    eleve_details = EleveSerializer(source='eleve', read_only=True)
    classe_details = ClasseSerializer(source='classe', read_only=True)
    pieces_jointes = PieceJointeSerializer(source='pieces', many=True, read_only=True)

    class Meta:
        model = Inscription
        fields = ['id', 'eleve', 'classe', 'annee_scolaire', 'numero', 'decision',
                  'moyenne_annuelle', 'date_inscription', 'eleve_details', 'classe_details',
                  'pieces_jointes']
        read_only_fields = ['annee_scolaire', 'numero', 'decision', 'moyenne_annuelle']
        validators = []   # unicité contrôlée dans validate()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        # Les documents du dossier ne concernent pas les enseignants
        if request is not None and not user_is_admin(request.user):
            data['pieces_jointes'] = []
        return data

    def validate(self, attrs):
        eleve, classe = attrs['eleve'], attrs['classe']
        annee = classe.annee_scolaire   # l'année est celle de la classe
        verifier_annee_ouverte(annee)

        deja = Inscription.objects.filter(eleve=eleve, annee_scolaire=annee).select_related('classe').first()
        if deja:
            raise serializers.ValidationError(
                f"{eleve.nom} {eleve.prenom} est déjà inscrit(e) en {deja.classe.nom} pour "
                f"l'année {annee.libelle} : un élève ne peut être que dans une seule classe."
            )
        verifier_admissibilite(eleve, classe)
        attrs['annee_scolaire'] = annee
        # pièces jointes facultatives (envoi multipart) : contrôlées avant toute création
        attrs['_pieces'] = lire_pieces_envoyees(self.context.get('request'))
        return attrs

    def create(self, validated_data):
        pieces = validated_data.pop('_pieces', [])
        auteur = getattr(self.context.get('request'), 'user', None)
        with transaction.atomic():
            inscription = super().create(validated_data)
            creer_pieces(inscription, pieces, auteur)
        return inscription


class AffectationSerializer(serializers.ModelSerializer):
    enseignant = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(profile__role='enseignant', profile__statut='valide'),
        error_messages={'does_not_exist': 'Enseignant introuvable ou non validé.'},
    )
    enseignant_nom = serializers.CharField(source='enseignant.get_full_name', read_only=True)
    enseignant_username = serializers.CharField(source='enseignant.username', read_only=True)
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)
    classe_nom = serializers.CharField(source='classe.nom', read_only=True)

    class Meta:
        model = Affectation
        fields = ['id', 'enseignant', 'matiere', 'classe', 'annee_scolaire',
                  'enseignant_nom', 'enseignant_username', 'matiere_nom', 'classe_nom']
        read_only_fields = ['annee_scolaire']
        validators = []

    def validate(self, attrs):
        inst = self.instance
        classe = attrs.get('classe', getattr(inst, 'classe', None))
        matiere = attrs.get('matiere', getattr(inst, 'matiere', None))
        enseignant = attrs.get('enseignant', getattr(inst, 'enseignant', None))
        annee = classe.annee_scolaire   # l'affectation vaut pour l'année de la classe

        if inst is None or inst.annee_scolaire_id != annee.id:
            verifier_annee_ouverte(annee)
        verifier_matiere_enseignee(matiere, classe)

        # Une matière n'a qu'UN SEUL enseignant dans une classe donnée
        autre = Affectation.objects.filter(
            matiere=matiere, classe=classe).select_related('enseignant')
        if inst:
            autre = autre.exclude(pk=inst.pk)
        deja = autre.first()
        if deja:
            if deja.enseignant_id == enseignant.id:
                raise serializers.ValidationError(
                    "Cet enseignant est déjà affecté à cette matière dans cette classe.")
            nom = deja.enseignant.get_full_name() or deja.enseignant.username
            raise serializers.ValidationError(
                f"{matiere.nom} est déjà confiée à {nom} en {classe.nom} : une matière n'a "
                f"qu'un seul enseignant par classe. Utilisez « Changer d'enseignant » "
                f"ou retirez d'abord l'affectation existante.")
        attrs['annee_scolaire'] = annee
        return attrs


# ---------------------------------------------------------------------------
# Configuration des matières d'un niveau
# ---------------------------------------------------------------------------
class ConfigEntreeSerializer(serializers.Serializer):
    matiere = serializers.PrimaryKeyRelatedField(queryset=Matiere.objects.all())
    coefficient = serializers.IntegerField(min_value=1, max_value=20)


class ConfigEcritureSerializer(serializers.Serializer):
    classe = serializers.PrimaryKeyRelatedField(queryset=Classe.objects.select_related('annee_scolaire'))
    matieres = ConfigEntreeSerializer(many=True, allow_empty=True)

    def validate_matieres(self, valeur):
        ids = [e['matiere'].id for e in valeur]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Une matière est présente plusieurs fois.')
        return valeur


class DecisionSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=['passant', 'redoublant'])


class ClotureSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
class NoteSerializer(serializers.ModelSerializer):
    """Lecture d'une note (avec les moyennes calculées)."""
    moyenne_journaliere = serializers.ReadOnlyField()
    moyenne_matiere = serializers.ReadOnlyField()
    eleve_nom = serializers.CharField(source='inscription.eleve.nom', read_only=True)
    eleve_prenom = serializers.CharField(source='inscription.eleve.prenom', read_only=True)
    matiere_nom = serializers.CharField(source='matiere.nom', read_only=True)

    class Meta:
        model = Note
        fields = ['id', 'inscription', 'matiere', 'trimestre',
                  'j1', 'j2', 'j3', 'examen',
                  'moyenne_journaliere', 'moyenne_matiere',
                  'eleve_nom', 'eleve_prenom', 'matiere_nom', 'updated_at']
        read_only_fields = fields


def _champ_note():
    return serializers.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=NOTE_MIN, max_value=NOTE_MAX,
        required=False, allow_null=True,
    )


class NoteUpsertSerializer(BlankToNullMixin, serializers.Serializer):
    """Validation de la saisie d'une note (création ou modification)."""
    blank_to_null = ('j1', 'j2', 'j3', 'examen')

    inscription = serializers.PrimaryKeyRelatedField(
        queryset=Inscription.objects.select_related('classe__annee_scolaire', 'eleve')
    )
    matiere = serializers.PrimaryKeyRelatedField(queryset=Matiere.objects.all())
    trimestre = serializers.ChoiceField(choices=Note.TRIMESTRE_CHOICES)
    j1 = _champ_note()
    j2 = _champ_note()
    j3 = _champ_note()
    examen = _champ_note()
