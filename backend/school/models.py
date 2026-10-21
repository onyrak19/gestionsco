import os
import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Max

from .niveaux import (
    CODES_NIVEAUX, construire_nom_classe, lettres_majuscules, rang_niveau,
)

# Barème : toutes les notes sont sur 20
NOTE_MIN = 0
NOTE_MAX = 20
NOTE_VALIDATORS = [MinValueValidator(NOTE_MIN), MaxValueValidator(NOTE_MAX)]


def arrondi(valeur):
    """Arrondi à 2 décimales, 0.005 arrondi vers le haut (12.125 -> 12.13),
    retourné sous forme de float (nombre JSON)."""
    return float(Decimal(str(valeur)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def chemin_photo(instance, nom_fichier):
    """Nom de fichier aléatoire : l'adresse d'une photo ne se devine pas."""
    return f"eleves/photos/{uuid.uuid4().hex}.jpg"


def chemin_piece(instance, nom_fichier):
    extension = os.path.splitext(nom_fichier)[1].lower()[:10]
    return f"pieces_jointes/{instance.inscription_id}/{uuid.uuid4().hex}{extension}"


class Etablissement(models.Model):
    """Informations de l'école (une seule fiche), utilisées dans les PDF."""
    nom = models.CharField(max_length=150, default='Établissement scolaire')
    adresse = models.CharField(max_length=255, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    directeur = models.CharField(max_length=150, blank=True)

    def __str__(self):
        return self.nom

    @classmethod
    def obtenir(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AnneeScolaire(models.Model):
    libelle = models.CharField(max_length=20, unique=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    active = models.BooleanField(default=False)
    cloturee = models.BooleanField(default=False)

    class Meta:
        ordering = ['-libelle']

    def __str__(self):
        return self.libelle

    def save(self, *args, **kwargs):
        # Une seule année active à la fois
        with transaction.atomic():
            if self.active:
                AnneeScolaire.objects.exclude(pk=self.pk).update(active=False)
            super().save(*args, **kwargs)


class Classe(models.Model):
    nom = models.CharField(max_length=50)
    # Niveau / série / numéro : le nom est construit automatiquement
    # (« Terminale L 1 »). Une classe créée avant cette évolution garde son nom
    # et un niveau vide.
    niveau = models.CharField(max_length=40, blank=True, default='')
    serie = models.CharField(max_length=20, blank=True, default='')
    numero = models.PositiveSmallIntegerField(default=1)
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='classes'
    )

    class Meta:
        unique_together = ('nom', 'annee_scolaire')
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.annee_scolaire})"

    def save(self, *args, **kwargs):
        if self.niveau:
            self.nom = construire_nom_classe(self.niveau, self.serie, self.numero)
        super().save(*args, **kwargs)

    @property
    def rang_niveau(self):
        return rang_niveau(self.niveau)

    @property
    def code(self):
        """Code court servant à fabriquer les matricules (TLE-L1, 6E-2...)."""
        if not self.niveau:
            return f"C{self.pk}"
        base = CODES_NIVEAUX.get(self.niveau) or lettres_majuscules(self.niveau) or 'CL'
        serie = lettres_majuscules(self.serie, 6) if self.serie else ''
        return f"{base}-{serie}{self.numero}"


class Matiere(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    # Coefficient utilisé tant qu'une classe n'a pas de configuration propre
    coefficient = models.IntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generer_code_matiere(self.nom, exclure_pk=self.pk)
        super().save(*args, **kwargs)


def generer_code_matiere(nom, exclure_pk=None):
    """Code automatique : 3 premières lettres (MAT), puis MAT2, MAT3... si pris."""
    base = lettres_majuscules(nom) or 'MAT'
    code, i = base, 2
    while Matiere.objects.filter(code=code).exclude(pk=exclure_pk).exists():
        code = f"{base}{i}"
        i += 1
    return code


class ConfigMatiere(models.Model):
    """Matières enseignées et coefficients d'un niveau (et d'une série) pour une
    année scolaire. S'applique à toutes les classes de même niveau et même série."""
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.CASCADE, related_name='configs_matieres'
    )
    niveau = models.CharField(max_length=40)
    serie = models.CharField(max_length=20, blank=True, default='')
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name='configs')
    coefficient = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(20)]
    )

    class Meta:
        unique_together = ('annee_scolaire', 'niveau', 'serie', 'matiere')
        ordering = ['matiere__nom']

    def __str__(self):
        return f"{self.niveau} {self.serie} : {self.matiere} x{self.coefficient}"


class Eleve(models.Model):
    SEXE_CHOICES = [('M', 'Masculin'), ('F', 'Féminin')]

    # Attribué automatiquement à la première inscription
    matricule = models.CharField(max_length=30, unique=True, null=True, blank=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField(null=True, blank=True)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, default='M')
    actif = models.BooleanField(default=True)
    # Parents ou tuteur (facultatifs) : nom et numéro de mobile
    parent_nom = models.CharField(max_length=150, blank=True, default='')
    parent_mobile = models.CharField(max_length=30, blank=True, default='')
    parent2_nom = models.CharField(max_length=150, blank=True, default='')
    parent2_mobile = models.CharField(max_length=30, blank=True, default='')
    # Photo facultative (réduite et convertie en JPEG à l'envoi)
    photo = models.ImageField(upload_to=chemin_photo, blank=True, default='')

    class Meta:
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.matricule or 'sans matricule'})"

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}".strip()

    @property
    def photo_token(self):
        """Change à chaque nouvelle photo : sert à rafraîchir l'image côté navigateur."""
        return os.path.splitext(os.path.basename(self.photo.name))[0] if self.photo else ''


class Inscription(models.Model):
    DECISION_CHOICES = [
        ('en_cours', 'En cours'),
        ('passant', 'Passant'),
        ('redoublant', 'Redoublant'),
        ('non_decide', 'Non décidé'),
    ]

    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='inscriptions')
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='inscriptions')
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='inscriptions')
    date_inscription = models.DateField(auto_now_add=True)
    # Numéro d'ordre dans la classe : le 1er inscrit a le n°1, etc.
    numero = models.PositiveIntegerField(null=True, blank=True)
    # Renseignés à la clôture de l'année
    decision = models.CharField(max_length=12, choices=DECISION_CHOICES, default='en_cours')
    moyenne_annuelle = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        unique_together = [('eleve', 'annee_scolaire'), ('classe', 'numero')]
        ordering = ['eleve__nom']

    def __str__(self):
        return f"{self.eleve} → {self.classe} ({self.annee_scolaire})"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            return super().save(*args, **kwargs)
        with transaction.atomic():
            if not self.annee_scolaire_id:
                self.annee_scolaire_id = self.classe.annee_scolaire_id
            if self.numero is None:
                dernier = Inscription.objects.filter(classe=self.classe).aggregate(m=Max('numero'))['m']
                self.numero = (dernier or 0) + 1
            super().save(*args, **kwargs)
            if not self.eleve.matricule:
                self.eleve.matricule = generer_matricule(self)
                self.eleve.save(update_fields=['matricule'])


class PieceJointe(models.Model):
    """Document joint à une inscription (acte de naissance, certificat...).
    Facultatif : une inscription peut en avoir zéro, une ou plusieurs."""
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name='pieces')
    libelle = models.CharField(max_length=120, blank=True, default='')
    fichier = models.FileField(upload_to=chemin_piece, max_length=255)
    nom_original = models.CharField(max_length=255)
    taille = models.PositiveIntegerField(default=0)
    type_mime = models.CharField(max_length=100, blank=True, default='')
    ajoute_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date_ajout', 'id']

    def __str__(self):
        return f"{self.libelle or self.nom_original} ({self.inscription})"


def generer_matricule(inscription):
    """Ex. TLE-L1-26-001 : classe, année (2 chiffres), numéro dans la classe."""
    annee = inscription.annee_scolaire.date_debut.year % 100
    base = f"{inscription.classe.code}-{annee:02d}-{inscription.numero:03d}"
    matricule, i = base, 2
    while Eleve.objects.filter(matricule=matricule).exists():
        matricule = f"{base}-{i}"
        i += 1
    return matricule


class Affectation(models.Model):
    enseignant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='affectations')
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name='affectations')
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='affectations')
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='affectations')

    class Meta:
        # une matière n'a qu'un seul enseignant dans une classe, pour une année
        unique_together = ('matiere', 'classe', 'annee_scolaire')

    def __str__(self):
        return f"{self.enseignant.username} → {self.matiere} → {self.classe}"


class Note(models.Model):
    TRIMESTRE_CHOICES = [(1, '1er trimestre'), (2, '2e trimestre'), (3, '3e trimestre')]

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name='notes')
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name='notes')
    trimestre = models.IntegerField(choices=TRIMESTRE_CHOICES)

    j1 = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, validators=NOTE_VALIDATORS
    )
    j2 = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, validators=NOTE_VALIDATORS
    )
    j3 = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, validators=NOTE_VALIDATORS
    )
    examen = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, validators=NOTE_VALIDATORS
    )

    saisi_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('inscription', 'matiere', 'trimestre')

    def __str__(self):
        return f"{self.inscription.eleve} - {self.matiere} - T{self.trimestre}"

    @property
    def moyenne_journaliere(self):
        """Moyenne des interrogations J1..J3 renseignées (une note à 0 compte)."""
        vals = [Decimal(str(v)) for v in (self.j1, self.j2, self.j3) if v is not None]
        if not vals:
            return None
        return arrondi(sum(vals) / len(vals))

    @property
    def moyenne_matiere(self):
        """(moyenne journalière + examen) / 2 ; si l'une des deux manque,
        on prend l'autre. Le calcul utilise la moyenne journalière non arrondie."""
        vals = [Decimal(str(v)) for v in (self.j1, self.j2, self.j3) if v is not None]
        mj = (sum(vals) / len(vals)) if vals else None
        ex = Decimal(str(self.examen)) if self.examen is not None else None
        if mj is None and ex is None:
            return None
        if mj is None:
            return arrondi(ex)
        if ex is None:
            return arrondi(mj)
        return arrondi((mj + ex) / 2)
