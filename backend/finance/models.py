"""Finances de l'établissement.

* Tarif            : droit d'inscription, écolage mensuel et autres frais, définis par
                     niveau (et série) pour une année scolaire, comme les matières.
* Paiement         : un encaissement d'élève (droit, écolage de un ou plusieurs mois, autre frais).
* CategorieFinance : catégories de dépenses et d'entrées d'argent (configurables).
* Mouvement        : une dépense ou une entrée d'argent (les imprévus sont signalés).
* Employe, AvanceSalaire, PaieSalaire : salaires, avances et retenues.

Les paiements annulés ne sont jamais supprimés : ils restent visibles (traçabilité).
"""
from django.conf import settings
from django.db import models

from school.models import AnneeScolaire, Inscription


def champ_montant(**options):
    return models.DecimalField(max_digits=12, decimal_places=2, **options)


# ---------------------------------------------------------------------------
# Tarifs par niveau
# ---------------------------------------------------------------------------
class Tarif(models.Model):
    TYPES = [
        ('droit', "Droit d'inscription"),
        ('ecolage', 'Écolage mensuel'),
        ('autre', 'Autre frais'),
    ]

    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='tarifs')
    niveau = models.CharField(max_length=40)
    serie = models.CharField(max_length=20, blank=True, default='')
    type = models.CharField(max_length=10, choices=TYPES)
    # Seulement pour « autre frais » (ex. Uniforme, Examen) ; vide pour droit et écolage
    libelle = models.CharField(max_length=100, blank=True, default='')
    montant = champ_montant()

    class Meta:
        unique_together = ('annee_scolaire', 'niveau', 'serie', 'type', 'libelle')
        ordering = ['niveau', 'serie', 'type', 'libelle']

    def __str__(self):
        return f"{self.niveau} {self.serie} {self.get_type_display()} {self.libelle} : {self.montant}"


# ---------------------------------------------------------------------------
# Paiements des élèves
# ---------------------------------------------------------------------------
MODES_PAIEMENT = [
    ('especes', 'Espèces'),
    ('mobile', 'Mobile money'),
    ('virement', 'Virement'),
    ('cheque', 'Chèque'),
]


class Paiement(models.Model):
    TYPES = [
        ('droit', "Droit d'inscription"),
        ('ecolage', 'Écolage'),
        ('autre', 'Autre frais'),
    ]

    numero = models.CharField(max_length=20, unique=True)
    # L'inscription peut disparaître plus tard : les noms sont recopiés pour garder le reçu lisible
    inscription = models.ForeignKey(
        Inscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    annee_scolaire = models.ForeignKey(
        AnneeScolaire, on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    eleve_nom = models.CharField(max_length=220)
    matricule = models.CharField(max_length=30, blank=True, default='')
    classe_nom = models.CharField(max_length=60, blank=True, default='')
    annee_libelle = models.CharField(max_length=20, blank=True, default='')

    type = models.CharField(max_length=10, choices=TYPES)
    date = models.DateField()
    mode = models.CharField(max_length=10, choices=MODES_PAIEMENT, default='especes')
    reference = models.CharField(max_length=100, blank=True, default='')
    observation = models.CharField(max_length=255, blank=True, default='')
    montant_total = champ_montant()

    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    annule = models.BooleanField(default=False, db_index=True)
    motif_annulation = models.CharField(max_length=255, blank=True, default='')
    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    annule_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.numero} — {self.eleve_nom} — {self.montant_total}"


class LignePaiement(models.Model):
    paiement = models.ForeignKey(Paiement, on_delete=models.CASCADE, related_name='lignes')
    libelle = models.CharField(max_length=150)
    # Premier jour du mois payé (écolage seulement)
    mois = models.DateField(null=True, blank=True)
    tarif = models.ForeignKey(Tarif, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    montant = champ_montant()

    class Meta:
        ordering = ['mois', 'id']

    def __str__(self):
        return f"{self.libelle} : {self.montant}"


# ---------------------------------------------------------------------------
# Dépenses et entrées d'argent
# ---------------------------------------------------------------------------
class CategorieFinance(models.Model):
    SENS = [('depense', 'Dépense'), ('entree', "Entrée d'argent")]

    nom = models.CharField(max_length=100)
    sens = models.CharField(max_length=10, choices=SENS)
    actif = models.BooleanField(default=True)

    class Meta:
        unique_together = ('sens', 'nom')
        ordering = ['sens', 'nom']
        verbose_name = 'catégorie'

    def __str__(self):
        return f"{self.get_sens_display()} : {self.nom}"


class Mouvement(models.Model):
    """Une dépense ou une entrée d'argent hors scolarité des élèves."""
    date = models.DateField(db_index=True)
    categorie = models.ForeignKey(CategorieFinance, on_delete=models.PROTECT, related_name='mouvements')
    libelle = models.CharField(max_length=200)
    montant = champ_montant()
    # Dépense non prévue (panne, réparation urgente...) : suivie à part dans le bilan
    imprevu = models.BooleanField(default=False)
    reference = models.CharField(max_length=100, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.date} {self.libelle} : {self.montant}"

    @property
    def sens(self):
        return self.categorie.sens


# ---------------------------------------------------------------------------
# Salaires
# ---------------------------------------------------------------------------
class Employe(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100, blank=True, default='')
    poste = models.CharField(max_length=100, blank=True, default='')
    telephone = models.CharField(max_length=30, blank=True, default='')
    salaire_mensuel = champ_montant(default=0)
    date_embauche = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    # Compte enseignant lié (facultatif)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['nom', 'prenom']

    def __str__(self):
        return self.nom_complet

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}".strip()


class AvanceSalaire(models.Model):
    """Argent remis à un employé avant sa paie ; retenu ensuite sur ses salaires."""
    employe = models.ForeignKey(Employe, on_delete=models.PROTECT, related_name='avances')
    date = models.DateField()
    montant = champ_montant()
    motif = models.CharField(max_length=255, blank=True, default='')
    annulee = models.BooleanField(default=False)
    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Avance {self.employe} {self.montant}"


class PaieSalaire(models.Model):
    numero = models.CharField(max_length=20, unique=True)
    employe = models.ForeignKey(Employe, on_delete=models.PROTECT, related_name='paies')
    employe_nom = models.CharField(max_length=220)
    poste = models.CharField(max_length=100, blank=True, default='')
    date = models.DateField(db_index=True)
    mode = models.CharField(max_length=10, choices=MODES_PAIEMENT, default='especes')
    salaire_mensuel = champ_montant(default=0)      # salaire de référence au moment du paiement

    montant_brut = champ_montant()
    retenue_avances = champ_montant(default=0)
    autres_retenues = champ_montant(default=0)
    motif_retenues = models.CharField(max_length=255, blank=True, default='')
    net_paye = champ_montant()

    exceptionnel = models.BooleanField(default=False)
    motif_exceptionnel = models.CharField(max_length=255, blank=True, default='')
    observation = models.CharField(max_length=255, blank=True, default='')

    saisi_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    annule = models.BooleanField(default=False, db_index=True)
    motif_annulation = models.CharField(max_length=255, blank=True, default='')
    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    annule_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.numero} — {self.employe_nom} — {self.net_paye}"


class LignePaie(models.Model):
    paie = models.ForeignKey(PaieSalaire, on_delete=models.CASCADE, related_name='lignes')
    mois = models.DateField()               # premier jour du mois payé
    montant = champ_montant(default=0)

    class Meta:
        ordering = ['mois', 'id']


class RetenueAvance(models.Model):
    """Part d'une avance retenue sur une paie."""
    paie = models.ForeignKey(PaieSalaire, on_delete=models.CASCADE, related_name='retenues')
    avance = models.ForeignKey(AvanceSalaire, on_delete=models.PROTECT, related_name='retenues')
    montant = champ_montant()
