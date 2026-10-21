"""Export et import de données au format Excel (.xlsx).

* EXPORT : chaque « jeu de données » (élèves, notes, classes...) devient une feuille
  du classeur ; on peut tout exporter ou choisir, et filtrer par année, classes, trimestre.
* IMPORT : une feuille Excel est lue ligne par ligne. Chaque ligne passe par les MÊMES
  règles que la saisie à l'écran (serializers) : aucune règle n'est contournée.
  L'aperçu exécute tout l'import puis annule (rollback) : il montre exactement ce qui
  se passerait, sans rien écrire.
"""
import logging
import re
from collections import defaultdict

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework.exceptions import ValidationError as ErreurDRF

from journal.models import Activite

from . import excel_outils as xo
from .calculs import ConfigResolver, resultats_classe
from .models import (
    AnneeScolaire, Affectation, Classe, ConfigMatiere, Eleve, Etablissement, Inscription, Matiere, Note,
)
from .niveaux import construire_nom_classe
from .serializers import (
    AffectationSerializer, ClasseSerializer, EleveSerializer, InscriptionSerializer,
    MatiereSerializer, NoteUpsertSerializer,
)

logger = logging.getLogger(__name__)

STATUTS = {'valide': 'Validé', 'en_attente': 'En attente', 'refuse': 'Refusé', 'desactive': 'Désactivé'}


def _nombre(valeur):
    return None if valeur is None else float(valeur)


# ===========================================================================
# FILTRES
# ===========================================================================
class Filtres:
    """annee : id ; classes : [ids] ; trimestre : 1, 2 ou 3 (tous vides = tout)."""

    def __init__(self, annee=None, classes=None, trimestre=None):
        self.annee = annee
        self.classes = classes or []
        self.trimestre = trimestre

    @classmethod
    def depuis(cls, donnees):
        def entier(valeur, nom):
            try:
                return int(valeur)
            except (TypeError, ValueError):
                raise ValueError(f"{nom} : valeur invalide.")
        annee = entier(donnees['annee'], 'annee') if donnees.get('annee') else None
        brut = donnees.get('classes') or []
        if not isinstance(brut, (list, tuple)):
            raise ValueError("classes : doit être une liste.")
        classes = [entier(c, 'classes') for c in brut]
        trimestre = entier(donnees['trimestre'], 'trimestre') if donnees.get('trimestre') else None
        if trimestre not in (None, 1, 2, 3):
            raise ValueError("trimestre : doit valoir 1, 2 ou 3.")
        return cls(annee, classes, trimestre)

    def resume(self):
        morceaux = []
        if self.annee:
            a = AnneeScolaire.objects.filter(pk=self.annee).first()
            morceaux.append(f"année {a.libelle if a else self.annee}")
        if self.classes:
            noms = list(Classe.objects.filter(pk__in=self.classes).order_by('nom').values_list('nom', flat=True))
            morceaux.append("classes : " + ', '.join(noms[:8]) + (' …' if len(noms) > 8 else ''))
        if self.trimestre:
            morceaux.append(f"trimestre {self.trimestre}")
        return ' · '.join(morceaux) if morceaux else 'aucun filtre (toutes les données)'


def _inscriptions(f):
    qs = Inscription.objects.all()
    if f.annee:
        qs = qs.filter(annee_scolaire_id=f.annee)
    if f.classes:
        qs = qs.filter(classe_id__in=f.classes)
    return qs


def _classes(f):
    qs = Classe.objects.select_related('annee_scolaire')
    if f.annee:
        qs = qs.filter(annee_scolaire_id=f.annee)
    if f.classes:
        qs = qs.filter(pk__in=f.classes)
    return qs


# ===========================================================================
# JEUX DE DONNÉES (export)
# ===========================================================================
class Jeu:
    cle = ''
    libelle = ''
    description = ''
    colonnes = ()
    importable = False

    def queryset(self, f):
        raise NotImplementedError

    def nombre(self, f):
        return self.queryset(f).count()

    def lignes(self, f):
        raise NotImplementedError


class JeuAnnees(Jeu):
    cle, libelle = 'annees', 'Années scolaires'
    description = "Les années scolaires, avec leurs dates, l'année en cours et l'état de clôture."
    colonnes = ('Année scolaire', 'Début', 'Fin', 'Année en cours', 'Clôturée')

    def queryset(self, f):
        qs = AnneeScolaire.objects.order_by('date_debut')
        return qs.filter(pk=f.annee) if f.annee else qs

    def lignes(self, f):
        for a in self.queryset(f):
            yield [a.libelle, a.date_debut, a.date_fin, 'Oui' if a.active else 'Non', 'Oui' if a.cloturee else 'Non']


class JeuMatieres(Jeu):
    cle, libelle, importable = 'matieres', 'Matières', True
    description = "La liste des matières et leur coefficient par défaut."
    colonnes = ('Matière', 'Coefficient par défaut')

    def queryset(self, f):
        return Matiere.objects.order_by('nom')

    def lignes(self, f):
        for m in self.queryset(f):
            yield [m.nom, m.coefficient]


class JeuConfigMatieres(Jeu):
    cle, libelle, importable = 'config_matieres', 'Matières par niveau', True
    description = "Les matières enseignées et leur coefficient pour chaque niveau (et série) de chaque année."
    colonnes = ('Année scolaire', 'Niveau', 'Série', 'Matière', 'Coefficient')

    def queryset(self, f):
        qs = ConfigMatiere.objects.select_related('annee_scolaire', 'matiere')
        if f.annee:
            qs = qs.filter(annee_scolaire_id=f.annee)
        return qs.order_by('annee_scolaire__date_debut', 'niveau', 'serie', 'matiere__nom')

    def lignes(self, f):
        for c in self.queryset(f):
            yield [c.annee_scolaire.libelle, c.niveau, c.serie, c.matiere.nom, c.coefficient]


class JeuClasses(Jeu):
    cle, libelle, importable = 'classes', 'Classes', True
    description = "Les classes de chaque année : niveau, série, numéro et effectif."
    colonnes = ('Année scolaire', 'Classe', 'Niveau', 'Série', 'Numéro', 'Effectif')

    def queryset(self, f):
        return _classes(f).annotate(eff=Count('inscriptions')).order_by('annee_scolaire__date_debut', 'nom')

    def lignes(self, f):
        for c in self.queryset(f):
            yield [c.annee_scolaire.libelle, c.nom, c.niveau, c.serie, c.numero, c.eff]


class JeuEleves(Jeu):
    cle, libelle, importable = 'eleves', 'Élèves', True
    description = "Tous les élèves : matricule, identité, date de naissance, sexe, parents ou tuteur."
    colonnes = ('Matricule', 'Nom', 'Prénom', 'Date de naissance', 'Sexe', 'Actif',
                'Parent / tuteur', 'Mobile parent', 'Parent / tuteur 2', 'Mobile parent 2')

    def queryset(self, f):
        qs = Eleve.objects.order_by('nom', 'prenom')
        if f.annee or f.classes:
            qs = qs.filter(id__in=_inscriptions(f).values('eleve_id'))
        return qs

    def lignes(self, f):
        for e in self.queryset(f):
            yield [e.matricule, e.nom, e.prenom, e.date_naissance, e.sexe, 'Oui' if e.actif else 'Non',
                   e.parent_nom, e.parent_mobile, e.parent2_nom, e.parent2_mobile]


class JeuInscriptions(Jeu):
    cle, libelle, importable = 'inscriptions', 'Inscriptions', True
    description = "Qui est inscrit dans quelle classe, avec son numéro, sa décision et sa moyenne annuelle."
    colonnes = ('Année scolaire', 'Classe', 'N°', 'Matricule', 'Nom', 'Prénom', 'Date de naissance',
                'Sexe', 'Décision', 'Moyenne annuelle', 'Pièces jointes')

    def queryset(self, f):
        return (_inscriptions(f).select_related('eleve', 'classe', 'annee_scolaire')
                .annotate(nb_pieces=Count('pieces'))
                .order_by('annee_scolaire__date_debut', 'classe__nom', 'numero'))

    def lignes(self, f):
        for i in self.queryset(f):
            e = i.eleve
            yield [i.annee_scolaire.libelle, i.classe.nom, i.numero, e.matricule, e.nom, e.prenom,
                   e.date_naissance, e.sexe, i.get_decision_display(), _nombre(i.moyenne_annuelle), i.nb_pieces]


class JeuNotes(Jeu):
    cle, libelle, importable = 'notes', 'Notes', True
    description = "Toutes les notes (J1, J2, J3, examen) avec les moyennes calculées, par matière et par trimestre."
    colonnes = ('Année scolaire', 'Classe', 'Matière', 'Trimestre', 'N°', 'Matricule', 'Nom', 'Prénom',
                'J1', 'J2', 'J3', 'Examen', 'Moyenne journalière', 'Moyenne matière')

    def queryset(self, f):
        qs = Note.objects.select_related(
            'inscription__eleve', 'inscription__classe', 'inscription__annee_scolaire', 'matiere')
        if f.annee:
            qs = qs.filter(inscription__annee_scolaire_id=f.annee)
        if f.classes:
            qs = qs.filter(inscription__classe_id__in=f.classes)
        if f.trimestre:
            qs = qs.filter(trimestre=f.trimestre)
        return qs.order_by('inscription__annee_scolaire__date_debut', 'inscription__classe__nom',
                           'trimestre', 'matiere__nom', 'inscription__numero')

    def lignes(self, f):
        for n in self.queryset(f):
            i, e = n.inscription, n.inscription.eleve
            yield [i.annee_scolaire.libelle, i.classe.nom, n.matiere.nom, n.trimestre, i.numero, e.matricule,
                   e.nom, e.prenom, _nombre(n.j1), _nombre(n.j2), _nombre(n.j3), _nombre(n.examen),
                   _nombre(n.moyenne_journaliere), _nombre(n.moyenne_matiere)]


class JeuResultats(Jeu):
    cle, libelle = 'resultats', 'Résultats'
    description = "Les moyennes générales de chaque élève (trimestres et année) et ses rangs, comme sur les bulletins."
    colonnes = ('Année scolaire', 'Classe', 'N°', 'Matricule', 'Nom', 'Prénom', 'Moyenne T1', 'Moyenne T2',
                'Moyenne T3', 'Moyenne annuelle', 'Rang T1', 'Rang T2', 'Rang T3', 'Rang annuel', 'Effectif',
                'Décision')

    def queryset(self, f):
        return _inscriptions(f)

    def lignes(self, f):
        resolver = ConfigResolver()
        for classe in _classes(f).order_by('annee_scolaire__date_debut', 'nom'):
            donnees = resultats_classe(classe, resolver)
            ordonnes = sorted(donnees['resultats'].values(), key=lambda r: (r['inscription'].numero or 0))
            for r in ordonnes:
                i, e, g, rg = r['inscription'], r['inscription'].eleve, r['generales'], r['rangs']
                yield [classe.annee_scolaire.libelle, classe.nom, i.numero, e.matricule, e.nom, e.prenom,
                       _nombre(g.get(1)), _nombre(g.get(2)), _nombre(g.get(3)), _nombre(r['annuelle']),
                       rg.get(1), rg.get(2), rg.get(3), rg.get('annuelle'), donnees['effectif'],
                       i.get_decision_display()]


class JeuEnseignants(Jeu):
    cle, libelle = 'enseignants', 'Enseignants'
    description = "Les comptes enseignants : identifiant, nom, email, statut (jamais les mots de passe)."
    colonnes = ('Identifiant', 'Nom', 'Prénom', 'Email', 'Statut')

    def queryset(self, f):
        return User.objects.filter(profile__role='enseignant').select_related('profile').order_by('last_name', 'first_name')

    def lignes(self, f):
        for u in self.queryset(f):
            yield [u.username, u.last_name, u.first_name, u.email, STATUTS.get(u.profile.statut, u.profile.statut)]


class JeuAffectations(Jeu):
    cle, libelle, importable = 'affectations', 'Affectations', True
    description = "Quel enseignant donne quelle matière dans quelle classe."
    colonnes = ('Année scolaire', 'Classe', 'Matière', 'Identifiant enseignant', 'Enseignant')

    def queryset(self, f):
        qs = Affectation.objects.select_related('enseignant', 'matiere', 'classe', 'annee_scolaire')
        if f.annee:
            qs = qs.filter(annee_scolaire_id=f.annee)
        if f.classes:
            qs = qs.filter(classe_id__in=f.classes)
        return qs.order_by('annee_scolaire__date_debut', 'classe__nom', 'matiere__nom')

    def lignes(self, f):
        for a in self.queryset(f):
            u = a.enseignant
            yield [a.annee_scolaire.libelle, a.classe.nom, a.matiere.nom, u.username,
                   u.get_full_name() or u.username]


class JeuJournal(Jeu):
    cle, libelle = 'journal', "Journal d'activité"
    description = "L'historique complet des actions (qui a fait quoi, quand)."
    colonnes = ('Date', 'Utilisateur', 'Rôle', 'Catégorie', 'Action', 'Description', 'Année scolaire',
                'Classe', 'Matière', 'Élève', 'Adresse IP')

    def queryset(self, f):
        qs = Activite.objects.order_by('-date', '-id')
        if f.annee:
            a = AnneeScolaire.objects.filter(pk=f.annee).first()
            qs = qs.filter(annee=a.libelle if a else '')
        return qs

    def lignes(self, f):
        for a in self.queryset(f).iterator():
            quand = timezone.localtime(a.date).replace(tzinfo=None, microsecond=0)
            yield [quand, a.utilisateur_nom, a.utilisateur_role, a.get_categorie_display(), a.get_action_display(),
                   a.description, a.annee, a.classe, a.matiere, a.eleve, a.adresse_ip]


JEUX = {j.cle: j for j in (
    JeuEleves(), JeuInscriptions(), JeuClasses(), JeuAnnees(), JeuMatieres(), JeuConfigMatieres(), JeuEnseignants(),
    JeuAffectations(), JeuNotes(), JeuResultats(), JeuJournal(),
)}
JEUX_IMPORTABLES = {cle: j for cle, j in JEUX.items() if j.importable}


def catalogue(f):
    return [{'cle': j.cle, 'libelle': j.libelle, 'description': j.description,
             'nombre': j.nombre(f), 'importable': j.importable} for j in JEUX.values()]


def construire_export(cles, f, utilisateur_nom=''):
    """Classeur Excel (octets) : une feuille « Résumé » puis une feuille par jeu choisi."""
    inconnus = [c for c in cles if c not in JEUX]
    if inconnus:
        raise ValueError(f"Jeu de données inconnu : {', '.join(inconnus)}.")
    cles = [c for c in JEUX if c in set(cles)]      # ordre stable
    if not cles:
        raise ValueError("Choisissez au moins un jeu de données à exporter.")

    classeur = xo.nouveau_classeur()
    resume = classeur.active
    resume.title = 'Résumé'
    comptes = []
    for cle in cles:
        jeu = JEUX[cle]
        lignes = list(jeu.lignes(f))
        xo.ecrire_feuille(classeur, jeu.libelle, list(jeu.colonnes), lignes)
        comptes.append((jeu.libelle, len(lignes), jeu.description))

    etab = Etablissement.objects.first()
    lignes_resume = [
        ('titre', 'Export Gestion Scolaire'),
        ('ligne', 'Établissement', getattr(etab, 'nom', '') or '—'),
        ('ligne', 'Exporté le', timezone.localtime().strftime('%d/%m/%Y à %H:%M')),
        ('ligne', 'Exporté par', utilisateur_nom or '—'),
        ('ligne', 'Filtres', f.resume()),
        ('texte', ''),
        ('entete', 'Feuille', 'Lignes', 'Contenu'),
    ] + [('ligne', nom, nb, desc) for nom, nb, desc in comptes]
    xo.ecrire_texte_libre(resume, lignes_resume, largeur_a=30, largeur_b=16)
    resume.column_dimensions['C'].width = 90
    return xo.octets(classeur), comptes


# ===========================================================================
# IMPORT
# ===========================================================================
ALIAS = {
    'annee': ('anneescolaire', 'annee', 'anscolaire', 'anneescol'),
    'classe': ('classe', 'nomdelaclasse'),
    'niveau': ('niveau',),
    'serie': ('serie',),
    'numero': ('numero', 'n', 'no', 'num', 'numerodanslaclasse', 'nodanslaclasse', 'nordre'),
    'nom': ('nom', 'nomdefamille', 'nomeleve'),
    'prenom': ('prenom', 'prenoms', 'prenomeleve'),
    'naissance': ('datedenaissance', 'naissance', 'datenaissance', 'nele', 'neele', 'dn'),
    'sexe': ('sexe', 'genre'),
    'matricule': ('matricule', 'mat'),
    'matiere': ('matiere', 'discipline', 'nomdelamatiere'),
    'coefficient': ('coefficientpardefaut', 'coefficient', 'coef'),
    'trimestre': ('trimestre', 'trim', 'periode'),
    'j1': ('j1',), 'j2': ('j2',), 'j3': ('j3',),
    'examen': ('examen', 'exam', 'composition', 'compo'),
    'identifiant': ('identifiantenseignant', 'identifiant', 'login', 'nomdutilisateur'),
    'parent': ('parenttuteur', 'parent', 'nomduparent', 'tuteur', 'nomdututeur'),
    'mobile': ('mobileparent', 'mobile', 'telephoneparent', 'mobiledututeur'),
    'parent2': ('parenttuteur2', 'parent2'),
    'mobile2': ('mobileparent2', 'mobile2'),
}

# colonnes indispensables (au moins un des alias) ; titre affiché si elle manque
OBLIGATOIRES = {
    'matieres': (('matiere', 'nom'),),
    'eleves': ('nom', 'prenom', 'sexe'),
    'classes': ('annee', 'niveau', 'numero'),
    'inscriptions': ('annee', 'classe', 'nom', 'prenom'),
    'notes': ('annee', 'classe', 'matiere', 'trimestre'),
    'affectations': ('annee', 'classe', 'matiere', 'identifiant'),
    'config_matieres': ('annee', 'niveau', 'matiere', 'coefficient'),
}
TITRES = {
    'annee': 'Année scolaire', 'classe': 'Classe', 'niveau': 'Niveau', 'serie': 'Série', 'numero': 'Numéro',
    'nom': 'Nom', 'prenom': 'Prénom', 'naissance': 'Date de naissance', 'sexe': 'Sexe',
    'matricule': 'Matricule', 'matiere': 'Matière', 'coefficient': 'Coefficient par défaut',
    'trimestre': 'Trimestre', 'j1': 'J1', 'j2': 'J2', 'j3': 'J3', 'examen': 'Examen',
    'identifiant': 'Identifiant enseignant',
}


# colonnes d'un fichier exporté qui n'ont pas à être importées (recalculées ou informatives)
CALCULEES = {'moyennejournaliere', 'moyennematiere', 'moyenneannuelle', 'decision', 'effectif', 'actif',
             'piecesjointes', 'statut', 'enseignant', 'dernièreclasse'}


class ErreurLigne(Exception):
    """Ligne refusée : le message est affiché tel quel à l'utilisateur."""


def _aplatir(detail):
    if isinstance(detail, dict):
        return ' ; '.join(_aplatir(v) for v in detail.values())
    if isinstance(detail, (list, tuple)):
        return ' '.join(_aplatir(v) for v in detail)
    return str(detail)


def _champ(row, cle):
    for alias in ALIAS[cle]:
        if alias in row and xo.texte(row[alias]) != '':
            return row[alias]
    return None


def _txt(row, cle):
    return xo.texte(_champ(row, cle))


def _sexe(valeur):
    t = xo.normaliser(valeur)
    if t in ('m', 'masculin', 'garcon', 'homme', 'h', 'g'):
        return 'M'
    if t in ('f', 'feminin', 'fille', 'femme'):
        return 'F'
    raise ErreurLigne(f"Sexe : « {xo.texte(valeur)} » non reconnu (écrivez M ou F).")


def _trimestre(valeur):
    t = xo.texte(valeur)
    m = re.fullmatch(r'\D*([123])\D*', t)
    if not m:
        raise ErreurLigne(f"Trimestre : « {t} » invalide (écrivez 1, 2 ou 3).")
    return int(m.group(1))


class Rapport:
    def __init__(self):
        self.total = 0
        self.crees = self.mis_a_jour = self.ignores = 0
        self.erreurs = []          # [(numéro de ligne, message)]
        self.infos = []
        self.colonnes_ignorees = []
        self.applique = False
        self.bloque = False        # des erreurs ont empêché l'import

    def en_dict(self, maximum=200):
        return {
            'total': self.total, 'crees': self.crees, 'mis_a_jour': self.mis_a_jour,
            'ignores': self.ignores, 'nb_erreurs': len(self.erreurs),
            'erreurs': [{'ligne': n, 'message': m} for n, m in self.erreurs[:maximum]],
            'infos': self.infos, 'colonnes_ignorees': self.colonnes_ignorees,
            'applique': self.applique, 'bloque': self.bloque,
        }


class Contexte:
    """Mémorise les recherches (années, classes, élèves...) pendant un import."""

    def __init__(self, utilisateur):
        self.utilisateur = utilisateur
        self.apres_succes = []      # actions de mise en cache, exécutées seulement si la ligne réussit
        self.eleves_crees = 0
        self._annees = None
        self._classes = {}
        self._matieres = None
        self._enseignants = None
        self._eleves = None
        self._inscrits = {}

    # -- années, classes, matières, enseignants
    def annee(self, libelle):
        if not libelle:
            raise ErreurLigne("Année scolaire : valeur manquante.")
        if self._annees is None:
            self._annees = {xo.normaliser(a.libelle): a for a in AnneeScolaire.objects.all()}
        a = self._annees.get(xo.normaliser(libelle))
        if a is None:
            raise ErreurLigne(f"Année scolaire « {libelle} » introuvable (créez-la d'abord dans « Années scolaires »).")
        return a

    def classe(self, annee, nom):
        if not nom:
            raise ErreurLigne("Classe : valeur manquante.")
        if annee.id not in self._classes:
            self._classes[annee.id] = {xo.normaliser(c.nom): c for c in Classe.objects.filter(annee_scolaire=annee)}
        c = self._classes[annee.id].get(xo.normaliser(nom))
        if c is None:
            raise ErreurLigne(f"Classe « {nom} » introuvable pour l'année {annee.libelle}.")
        return c

    def classe_si_existe(self, annee, nom):
        try:
            return self.classe(annee, nom)
        except ErreurLigne:
            return None

    def ajouter_classe(self, classe):
        self.classe_si_existe(classe.annee_scolaire, classe.nom)   # charge le cache de l'année
        self._classes[classe.annee_scolaire_id][xo.normaliser(classe.nom)] = classe

    def matiere(self, nom):
        if not nom:
            raise ErreurLigne("Matière : valeur manquante.")
        if self._matieres is None:
            self._matieres = {xo.normaliser(m.nom): m for m in Matiere.objects.all()}
        m = self._matieres.get(xo.normaliser(nom))
        if m is None:
            raise ErreurLigne(f"Matière « {nom} » introuvable (créez-la d'abord dans « Matières »).")
        return m

    def matiere_si_existe(self, nom):
        try:
            return self.matiere(nom)
        except ErreurLigne:
            return None

    def ajouter_matiere(self, matiere):
        self.matiere_si_existe(matiere.nom)
        self._matieres[xo.normaliser(matiere.nom)] = matiere

    def enseignant(self, identifiant):
        if not identifiant:
            raise ErreurLigne("Identifiant enseignant : valeur manquante.")
        if self._enseignants is None:
            self._enseignants = {
                u.username.lower(): u for u in User.objects.filter(profile__role='enseignant', profile__statut='valide')}
        u = self._enseignants.get(identifiant.strip().lower())
        if u is None:
            raise ErreurLigne(f"Enseignant « {identifiant} » introuvable ou compte non validé.")
        return u

    # -- élèves
    def _index_eleves(self):
        if self._eleves is None:
            self._eleves = defaultdict(list)
            for e in Eleve.objects.all():
                self._eleves[(xo.normaliser(e.nom), xo.normaliser(e.prenom))].append(e)
        return self._eleves

    def trouver_eleve(self, nom, prenom, naissance):
        """L'élève déjà enregistré qui correspond, ou None. Plusieurs candidats sans
        date de naissance pour les départager : erreur explicite."""
        candidats = self._index_eleves().get((xo.normaliser(nom), xo.normaliser(prenom)), [])
        if naissance:
            exacts = [e for e in candidats if e.date_naissance == naissance]
            if exacts:
                return exacts[0]
            sans_date = [e for e in candidats if e.date_naissance is None]
            return sans_date[0] if len(sans_date) == 1 else None
        if len(candidats) > 1:
            raise ErreurLigne(
                f"Plusieurs élèves s'appellent « {nom} {prenom} » : ajoutez la date de naissance pour les distinguer.")
        return candidats[0] if candidats else None

    def ajouter_eleve(self, eleve):
        self._index_eleves()[(xo.normaliser(eleve.nom), xo.normaliser(eleve.prenom))].append(eleve)

    def inscrits(self, classe):
        """Index des inscrits d'une classe : par numéro, matricule, et (nom, prénom)."""
        if classe.id not in self._inscrits:
            par_numero, par_matricule, par_nom = {}, {}, defaultdict(list)
            for i in Inscription.objects.filter(classe=classe).select_related('eleve'):
                par_numero[i.numero] = i
                if i.eleve.matricule:
                    par_matricule[xo.normaliser(i.eleve.matricule)] = i
                par_nom[(xo.normaliser(i.eleve.nom), xo.normaliser(i.eleve.prenom))].append(i)
            self._inscrits[classe.id] = (par_numero, par_matricule, par_nom)
        return self._inscrits[classe.id]


def _valider(serializer):
    if not serializer.is_valid():
        raise ErreurLigne(_aplatir(serializer.errors))
    return serializer


# ---- une fonction par jeu : retourne 'cree', 'maj' ou 'ignore' ------------------------------
def _importer_matieres(ctx, row):
    nom = _txt(row, 'matiere') or xo.texte(row.get('nom'))
    if not nom:
        raise ErreurLigne("Matière : le nom est obligatoire.")
    coef = xo.entier(_champ(row, 'coefficient'), 'Coefficient')
    existante = ctx.matiere_si_existe(nom)
    if existante:
        if coef is None or coef == existante.coefficient:
            return 'ignore'
        _valider(MatiereSerializer(existante, data={'coefficient': coef}, partial=True)).save()
        return 'maj'
    matiere = _valider(MatiereSerializer(data={'nom': nom, 'coefficient': 1 if coef is None else coef})).save()
    ctx.apres_succes.append(lambda: ctx.ajouter_matiere(matiere))
    return 'cree'


def _creer_ou_trouver_eleve(ctx, row, creer):
    nom, prenom = _txt(row, 'nom'), _txt(row, 'prenom')
    if not nom or not prenom:
        raise ErreurLigne("Nom et prénom sont obligatoires.")
    naissance = xo.analyser_date(_champ(row, 'naissance'), 'Date de naissance')
    eleve = ctx.trouver_eleve(nom, prenom, naissance)
    if eleve:
        return eleve, False
    if not creer:
        return None, False
    sexe_brut = _champ(row, 'sexe')
    if sexe_brut is None:
        raise ErreurLigne(f"{nom} {prenom} n'existe pas encore : la colonne Sexe est nécessaire pour le créer.")
    donnees = {'nom': nom, 'prenom': prenom, 'sexe': _sexe(sexe_brut), **_parents(row)}
    if naissance:
        donnees['date_naissance'] = naissance.isoformat()
    eleve = _valider(EleveSerializer(data=donnees)).save()
    ctx.apres_succes.append(lambda: (ctx.ajouter_eleve(eleve), setattr(ctx, 'eleves_crees', ctx.eleves_crees + 1)))
    return eleve, True


def _parents(row):
    """Champs parents / tuteur présents (non vides) dans la ligne."""
    resultat = {}
    for champ, cle in (('parent_nom', 'parent'), ('parent_mobile', 'mobile'),
                       ('parent2_nom', 'parent2'), ('parent2_mobile', 'mobile2')):
        valeur = _txt(row, cle)
        if valeur:
            resultat[champ] = valeur
    return resultat


def _importer_eleves(ctx, row):
    eleve, cree = _creer_ou_trouver_eleve(ctx, row, creer=True)
    if cree:
        return 'cree'
    nouveaux = {c: v for c, v in _parents(row).items() if getattr(eleve, c) != v}
    if not nouveaux:
        return 'ignore'
    _valider(EleveSerializer(eleve, data=nouveaux, partial=True)).save()
    return 'maj'


def _importer_config_matieres(ctx, row):
    annee = ctx.annee(_txt(row, 'annee'))
    if annee.cloturee:
        raise ErreurLigne(f"L'année {annee.libelle} est clôturée : configuration figée.")
    niveau, serie = _txt(row, 'niveau'), _txt(row, 'serie').upper()
    if not niveau:
        raise ErreurLigne("Niveau : valeur manquante.")
    matiere = ctx.matiere(_txt(row, 'matiere'))
    coef = xo.entier(_champ(row, 'coefficient'), 'Coefficient')
    if coef is None or not 1 <= coef <= 20:
        raise ErreurLigne("Coefficient : un nombre entier entre 1 et 20 est obligatoire.")
    existante = ConfigMatiere.objects.filter(
        annee_scolaire=annee, niveau=niveau, serie=serie, matiere=matiere).first()
    if existante:
        if existante.coefficient == coef:
            return 'ignore'
        existante.coefficient = coef
        existante.save(update_fields=['coefficient'])
        return 'maj'
    ConfigMatiere.objects.create(annee_scolaire=annee, niveau=niveau, serie=serie, matiere=matiere, coefficient=coef)
    return 'cree'


def _importer_classes(ctx, row):
    annee = ctx.annee(_txt(row, 'annee'))
    niveau, serie = _txt(row, 'niveau'), _txt(row, 'serie').upper()
    numero = xo.entier(_champ(row, 'numero'), 'Numéro')
    if numero is None:
        raise ErreurLigne("Numéro : obligatoire (1 pour la première classe du niveau).")
    nom = construire_nom_classe(niveau, serie, numero)
    if ctx.classe_si_existe(annee, nom):
        return 'ignore'
    donnees = {'niveau': niveau, 'serie': serie, 'numero': numero, 'annee_scolaire': annee.id}
    classe = _valider(ClasseSerializer(data=donnees)).save()
    ctx.apres_succes.append(lambda: ctx.ajouter_classe(classe))
    return 'cree'


def _importer_inscriptions(ctx, row):
    annee = ctx.annee(_txt(row, 'annee'))
    classe = ctx.classe(annee, _txt(row, 'classe'))
    eleve, _nouveau = _creer_ou_trouver_eleve(ctx, row, creer=True)
    existante = Inscription.objects.filter(eleve=eleve, annee_scolaire=classe.annee_scolaire).first()
    if existante:
        if existante.classe_id == classe.id:
            return 'ignore'
        raise ErreurLigne(f"{eleve.nom_complet} est déjà inscrit en {existante.classe.nom} cette année.")
    _valider(InscriptionSerializer(data={'eleve': eleve.id, 'classe': classe.id}, context={})).save()
    return 'cree'


def _trouver_inscription(ctx, classe, row):
    par_numero, par_matricule, par_nom = ctx.inscrits(classe)
    matricule, numero = _txt(row, 'matricule'), xo.entier(_champ(row, 'numero'), 'N°')
    nom, prenom = _txt(row, 'nom'), _txt(row, 'prenom')
    if matricule:
        ins = par_matricule.get(xo.normaliser(matricule))
        if ins:
            return ins
        raise ErreurLigne(f"Matricule « {matricule} » introuvable dans {classe.nom}.")
    if numero is not None:
        ins = par_numero.get(numero)
        if ins:
            return ins
        raise ErreurLigne(f"Aucun élève n° {numero} dans {classe.nom}.")
    if nom and prenom:
        trouves = par_nom.get((xo.normaliser(nom), xo.normaliser(prenom)), [])
        if len(trouves) == 1:
            return trouves[0]
        if not trouves:
            raise ErreurLigne(f"« {nom} {prenom} » n'est pas inscrit dans {classe.nom}.")
        raise ErreurLigne(f"Plusieurs élèves s'appellent « {nom} {prenom} » dans {classe.nom} : utilisez le N° ou le matricule.")
    raise ErreurLigne("Indiquez l'élève : N°, matricule, ou nom et prénom.")


def _importer_notes(ctx, row):
    annee = ctx.annee(_txt(row, 'annee'))
    classe = ctx.classe(annee, _txt(row, 'classe'))
    matiere = ctx.matiere(_txt(row, 'matiere'))
    trimestre = _trimestre(_champ(row, 'trimestre'))
    inscription = _trouver_inscription(ctx, classe, row)

    champs = ('j1', 'j2', 'j3', 'examen')
    fournies = {}
    for c in champs:
        v = xo.nombre_decimal(_champ(row, c), c.upper() if c != 'examen' else 'Examen')
        if v is not None:
            fournies[c] = str(v)
    existante = Note.objects.filter(inscription=inscription, matiere=matiere, trimestre=trimestre).first()

    # Une case vide ne modifie jamais une note existante
    complet = {c: fournies.get(c, getattr(existante, c, None) if existante else None) for c in champs}
    donnees = {'inscription': inscription.id, 'matiere': matiere.id, 'trimestre': trimestre,
               **{c: (None if v is None else str(v)) for c, v in complet.items()}}
    valide = _valider(NoteUpsertSerializer(data=donnees)).validated_data

    if classe.annee_scolaire.cloturee:
        raise ErreurLigne(f"L'année {classe.annee_scolaire.libelle} est clôturée : les notes ne sont plus modifiables.")
    if ConfigResolver().coefficient(matiere, classe) is None:
        raise ErreurLigne(f"{matiere.nom} n'est pas enseignée en {classe.nom} (voir la configuration des matières de la classe).")

    if not fournies:
        return 'ignore'
    if existante and all(getattr(existante, c) == valide.get(c) for c in champs):
        return 'ignore'
    Note.objects.update_or_create(
        inscription=inscription, matiere=matiere, trimestre=trimestre,
        defaults={**{c: valide.get(c) for c in champs}, 'saisi_par': ctx.utilisateur},
    )
    return 'maj' if existante else 'cree'


def _importer_affectations(ctx, row):
    annee = ctx.annee(_txt(row, 'annee'))
    classe = ctx.classe(annee, _txt(row, 'classe'))
    matiere = ctx.matiere(_txt(row, 'matiere'))
    enseignant = ctx.enseignant(_txt(row, 'identifiant'))
    if Affectation.objects.filter(classe=classe, matiere=matiere, enseignant=enseignant).exists():
        return 'ignore'
    _valider(AffectationSerializer(data={
        'enseignant': enseignant.id, 'matiere': matiere.id, 'classe': classe.id})).save()
    return 'cree'


FONCTIONS = {
    'matieres': _importer_matieres, 'eleves': _importer_eleves, 'classes': _importer_classes,
    'inscriptions': _importer_inscriptions, 'notes': _importer_notes, 'affectations': _importer_affectations,
    'config_matieres': _importer_config_matieres,
}


def _colonnes_manquantes(cle, presentes):
    manquantes = []
    for besoin in OBLIGATOIRES[cle]:
        groupe = besoin if isinstance(besoin, tuple) else (besoin,)
        trouve = any(alias in presentes for g in groupe for alias in (ALIAS.get(g, (g,))))
        if not trouve:
            manquantes.append(TITRES.get(groupe[0], groupe[0]))
    return manquantes


def importer(cle, entetes, lignes, utilisateur, appliquer=False, ignorer_erreurs=False):
    """Traite les lignes lues par `excel_outils.lire_classeur`.

    appliquer=False : simple aperçu, rien n'est écrit.
    appliquer=True  : écrit tout, sauf s'il y a des erreurs (à moins de les ignorer)."""
    if cle not in FONCTIONS:
        raise ValueError("Ce type de données ne peut pas être importé.")
    rapport = Rapport()
    rapport.total = len(lignes)

    presentes = {xo.normaliser(e) for e in entetes if xo.normaliser(e)}
    manquantes = _colonnes_manquantes(cle, presentes)
    if manquantes:
        rapport.erreurs.append((1, "Colonne manquante : " + ', '.join(f"« {m} »" for m in manquantes)
                                + ". Téléchargez le modèle Excel pour voir les colonnes attendues."))
        rapport.bloque = True
        return rapport
    connus = {a for alias in ALIAS.values() for a in alias} | {'nom'} | CALCULEES
    rapport.colonnes_ignorees = [e for e in entetes if e and xo.normaliser(e) not in connus]

    ctx = Contexte(utilisateur)
    fonction = FONCTIONS[cle]
    with transaction.atomic():
        for numero, row in lignes:
            ctx.apres_succes = []
            try:
                with transaction.atomic():          # point de sauvegarde : une ligne refusée n'abîme pas les autres
                    resultat = fonction(ctx, row)
            except (ErreurLigne, ValueError) as exc:
                rapport.erreurs.append((numero, str(exc)))
                continue
            except ErreurDRF as exc:
                rapport.erreurs.append((numero, _aplatir(exc.detail)))
                continue
            except Exception:   # noqa: BLE001
                logger.exception("Import Excel (%s), ligne %s", cle, numero)
                rapport.erreurs.append((numero, "Ligne refusée (erreur inattendue)."))
                continue
            for action in ctx.apres_succes:
                action()
            if resultat == 'cree':
                rapport.crees += 1
            elif resultat == 'maj':
                rapport.mis_a_jour += 1
            else:
                rapport.ignores += 1

        if ctx.eleves_crees:
            rapport.infos.append(f"{ctx.eleves_crees} nouvel élève{'s' if ctx.eleves_crees > 1 else ''} ajouté{'s' if ctx.eleves_crees > 1 else ''}.")
        if not appliquer:
            transaction.set_rollback(True)
        elif rapport.erreurs and not ignorer_erreurs:
            rapport.bloque = True
            transaction.set_rollback(True)
        else:
            rapport.applique = True
    return rapport


# ===========================================================================
# MODÈLES À TÉLÉCHARGER
# ===========================================================================
# (titre de colonne, obligatoire, explication, exemple)
MODELES = {
    'eleves': {
        'resume': "Ajoute des élèves à l'application. Un élève déjà présent (même nom, prénom et date de naissance) n'est pas recréé : seules ses informations de parents / tuteur sont complétées.",
        'colonnes': [
            ('Nom', True, "Nom de famille", 'RAKOTO'),
            ('Prénom', True, "Prénom", 'Jean'),
            ('Date de naissance', False, "JJ/MM/AAAA (conseillée pour distinguer deux élèves homonymes)", '14/03/2012'),
            ('Sexe', True, "M ou F", 'M'),
            ('Parent / tuteur', False, "Nom du parent ou du tuteur", 'RAKOTO Paul'),
            ('Mobile parent', False, "Numéro de mobile du parent ou tuteur", '034 12 345 67'),
            ('Parent / tuteur 2', False, "Second parent ou tuteur (facultatif)", ''),
            ('Mobile parent 2', False, "Mobile du second parent (facultatif)", ''),
        ],
        'notes': ["Le matricule est attribué automatiquement lors de l'inscription dans une classe."],
    },
    'matieres': {
        'resume': "Crée des matières ou met à jour leur coefficient par défaut.",
        'colonnes': [
            ('Matière', True, "Nom de la matière", 'Sciences de la vie et de la Terre'),
            ('Coefficient par défaut', False, "Nombre entier supérieur ou égal à 1 (1 si vide)", 3),
        ],
        'notes': ["Une matière qui existe déjà garde son nom ; son coefficient est mis à jour s'il est différent."],
    },
    'config_matieres': {
        'resume': "Définit les matières enseignées (et leur coefficient) pour un niveau d'une année scolaire.",
        'colonnes': [
            ('Année scolaire', True, "Comme dans l'application", '2026-2027'),
            ('Niveau', True, "6ème, 5ème, Terminale…", '6ème'),
            ('Série', False, "Pour les niveaux à série (Première, Terminale) : L, S, OSE", ''),
            ('Matière', True, "Nom exact d'une matière existante", 'Mathématiques'),
            ('Coefficient', True, "Entier de 1 à 20", 3),
        ],
        'notes': ["Les matières doivent déjà exister (importez d'abord « Matières »). L'année ne doit pas être clôturée."],
    },
    'classes': {
        'resume': "Crée des classes pour une année scolaire (qui doit déjà exister).",
        'colonnes': [
            ('Année scolaire', True, "Comme dans l'application", '2026-2027'),
            ('Niveau', True, "6ème, 5ème, 4ème, 3ème, Seconde, Première, Terminale…", '6ème'),
            ('Série', False, "Obligatoire pour certains niveaux (ex. Terminale : L, S, OSE)", ''),
            ('Numéro', True, "1 pour la première classe du niveau, 2 pour la deuxième…", 1),
        ],
        'notes': ["Une classe qui existe déjà est ignorée."],
    },
    'inscriptions': {
        'resume': "Inscrit des élèves dans des classes. Les élèves qui n'existent pas encore sont créés automatiquement.",
        'colonnes': [
            ('Année scolaire', True, "Comme dans l'application", '2026-2027'),
            ('Classe', True, "Nom exact de la classe", '6ème 1'),
            ('Nom', True, "Nom de famille", 'RAKOTO'),
            ('Prénom', True, "Prénom", 'Jean'),
            ('Date de naissance', False, "JJ/MM/AAAA", '14/03/2012'),
            ('Sexe', False, "M ou F — obligatoire seulement si l'élève n'existe pas encore", 'M'),
        ],
        'notes': [
            "Le numéro dans la classe suit l'ordre des lignes du fichier ; le matricule est attribué automatiquement.",
            "Un élève déjà inscrit dans la même classe est ignoré ; déjà inscrit dans une autre classe la même année, la ligne est refusée.",
        ],
    },
    'notes': {
        'resume': "Saisit ou met à jour des notes. Les classes, matières et élèves doivent déjà exister.",
        'colonnes': [
            ('Année scolaire', True, "Comme dans l'application", '2026-2027'),
            ('Classe', True, "Nom exact de la classe", '6ème 1'),
            ('Matière', True, "Nom exact de la matière", 'Mathématiques'),
            ('Trimestre', True, "1, 2 ou 3", 1),
            ('N°', False, "Numéro de l'élève dans la classe (ou utilisez Matricule, ou Nom + Prénom)", 1),
            ('Matricule', False, "Autre façon d'identifier l'élève", ''),
            ('Nom', False, "Avec Prénom, si ni N° ni Matricule", ''),
            ('Prénom', False, "Avec Nom, si ni N° ni Matricule", ''),
            ('J1', False, "Note sur 20 (virgule ou point)", 12.5),
            ('J2', False, "Note sur 20", 14),
            ('J3', False, "Note sur 20", ''),
            ('Examen', False, "Note sur 20", 15),
        ],
        'notes': [
            "Une case de note vide ne modifie pas la note existante : pour corriger, saisissez la nouvelle valeur.",
            "Les notes doivent être comprises entre 0 et 20 ; la matière doit être enseignée dans la classe.",
            "Les colonnes de moyennes d'un fichier exporté sont ignorées : elles sont recalculées.",
        ],
    },
    'affectations': {
        'resume': "Affecte des enseignants à des matières dans des classes. Une matière n'a qu'un seul enseignant par classe.",
        'colonnes': [
            ('Année scolaire', True, "Comme dans l'application", '2026-2027'),
            ('Classe', True, "Nom exact de la classe", '6ème 1'),
            ('Matière', True, "Nom exact de la matière", 'Mathématiques'),
            ('Identifiant enseignant', True, "Identifiant de connexion d'un enseignant validé", 'jmartin'),
        ],
        'notes': ["Si la matière a déjà un autre enseignant dans cette classe, la ligne est refusée : changez-le dans l'écran Affectations."],
    },
}


def construire_modele(cle):
    """Classeur Excel vide à remplir : feuille de données (titres colorés) + mode d'emploi."""
    if cle not in MODELES:
        raise ValueError("Pas de modèle pour ce type de données.")
    m = MODELES[cle]
    jeu = JEUX[cle]
    titres = [c[0] for c in m['colonnes']]
    obligatoires = [c[0] for c in m['colonnes'] if c[1]]

    classeur = xo.nouveau_classeur()
    xo.ecrire_feuille(classeur, jeu.libelle, titres, [], obligatoires=obligatoires, premiere=True)

    mode = classeur.create_sheet("Mode d'emploi")
    lignes = [
        ('titre', f"Importer : {jeu.libelle}"),
        ('texte', m['resume']),
        ('texte', ''),
        ('texte', "Remplissez la première feuille à partir de la ligne 2 (la ligne 1 contient les titres, ne les modifiez pas)."),
        ('texte', "Les titres en bleu vif sont obligatoires. Effacez toute ligne d'exemple avant d'importer."),
    ]
    for note in m['notes']:
        lignes.append(('texte', "• " + note))
    lignes += [
        ('texte', ''),
        ('entete', 'Colonne', 'Obligatoire', 'Explication', 'Exemple'),
    ]
    for titre, obligatoire, aide, exemple in m['colonnes']:
        lignes.append(('ligne', titre, 'Oui' if obligatoire else 'Non', aide, exemple))
    lignes += [
        ('texte', ''),
        ('texte', "Exemple de ligne remplie (à ne pas recopier telle quelle) :"),
        ('entete', *titres),
        ('ligne', *[c[3] for c in m['colonnes']]),
    ]
    xo.ecrire_texte_libre(mode, lignes, largeur_a=26, largeur_b=14)
    mode.column_dimensions['C'].width = 60
    mode.column_dimensions['D'].width = 26
    return xo.octets(classeur)
