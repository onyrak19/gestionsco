"""Calculs de moyennes, classements et décisions de fin d'année."""
from collections import defaultdict

from django.conf import settings
from django.db import transaction

from .models import ConfigMatiere, Matiere, Note, arrondi

TRIMESTRES = (1, 2, 3)


def moyenne_ponderee(couples):
    """couples : liste de (moyenne, coefficient). Retourne la moyenne
    pondérée par les coefficients, ou None s'il n'y a rien à calculer."""
    total_coef = sum(coef for moy, coef in couples if moy is not None)
    if not total_coef:
        return None
    return arrondi(sum(moy * coef for moy, coef in couples if moy is not None) / total_coef)


def appreciation(moyenne):
    if moyenne is None:
        return ''
    if moyenne >= 16:
        return 'Excellent'
    if moyenne >= 14:
        return 'Très bien'
    if moyenne >= 12:
        return 'Bien'
    if moyenne >= 10:
        return 'Assez bien'
    if moyenne >= 8:
        return 'Insuffisant'
    return 'Très insuffisant'


class ConfigResolver:
    """Matières enseignées + coefficients d'une classe.

    Si l'admin a configuré le niveau (et la série) pour l'année : seules les
    matières configurées comptent, avec leur coefficient. Sinon (classe non
    configurée) : toutes les matières, avec leur coefficient par défaut."""

    def __init__(self):
        self._cache = {}

    def _charger(self, annee_id):
        if annee_id not in self._cache:
            configs = defaultdict(dict)
            for c in ConfigMatiere.objects.filter(annee_scolaire_id=annee_id):
                configs[(c.niveau, c.serie)][c.matiere_id] = c.coefficient
            self._cache[annee_id] = configs
        return self._cache[annee_id]

    def config(self, classe):
        """{matiere_id: coefficient}, ou None si la classe n'est pas configurée."""
        if not classe.niveau:
            return None
        return self._charger(classe.annee_scolaire_id).get((classe.niveau, classe.serie)) or None

    def coefficient(self, matiere, classe):
        """Coefficient de la matière dans la classe ; None = matière non enseignée."""
        cfg = self.config(classe)
        if cfg is None:
            return matiere.coefficient
        return cfg.get(matiere.id)


def resultats_classe(classe, resolver=None):
    """Résultats de toute une classe, calculés en une passe.

    Retourne {'matieres': [(matiere, coef)], 'effectif', 'stats', 'resultats'}
    où resultats[inscription_id] = {inscription, generales{1,2,3}, annuelle,
    rangs{1,2,3,'annuelle'}, notes{trimestre: {matiere_id: Note}}}."""
    resolver = resolver or ConfigResolver()
    inscriptions = list(classe.inscriptions.select_related('eleve', 'annee_scolaire'))

    notes_par = defaultdict(lambda: defaultdict(dict))
    matieres = {}
    for n in Note.objects.filter(inscription__classe=classe).select_related('matiere'):
        if resolver.coefficient(n.matiere, classe) is None:
            continue  # matière retirée de la configuration : ignorée
        notes_par[n.inscription_id][n.trimestre][n.matiere_id] = n
        matieres[n.matiere_id] = n.matiere

    cfg = resolver.config(classe)
    if cfg:
        matieres = {m.id: m for m in Matiere.objects.filter(id__in=cfg.keys())}
    liste_matieres = [(m, resolver.coefficient(m, classe))
                      for m in sorted(matieres.values(), key=lambda m: m.nom.lower())]

    resultats = {}
    for ins in inscriptions:
        generales = {}
        for t in TRIMESTRES:
            couples = [
                (n.moyenne_matiere, resolver.coefficient(n.matiere, classe))
                for n in notes_par[ins.id][t].values()
                if n.moyenne_matiere is not None
            ]
            g = moyenne_ponderee(couples)
            if g is not None:
                generales[t] = g
        annuelle = arrondi(sum(generales.values()) / len(generales)) if generales else None
        resultats[ins.id] = {
            'inscription': ins, 'generales': generales, 'annuelle': annuelle,
            'notes': notes_par[ins.id], 'rangs': {},
        }

    stats = {}
    for cle in (*TRIMESTRES, 'annuelle'):
        valeurs = {
            i: (r['annuelle'] if cle == 'annuelle' else r['generales'].get(cle))
            for i, r in resultats.items()
        }
        presentes = [v for v in valeurs.values() if v is not None]
        for i, v in valeurs.items():
            if v is not None:
                # rang « à égalité » : deux élèves à la même moyenne ont le même rang
                resultats[i]['rangs'][cle] = 1 + sum(1 for x in presentes if x > v)
        stats[cle] = {
            'moyenne': arrondi(sum(presentes) / len(presentes)) if presentes else None,
            'max': max(presentes) if presentes else None,
            'min': min(presentes) if presentes else None,
            'nb': len(presentes),
        }

    return {
        'matieres': liste_matieres, 'effectif': len(inscriptions),
        'stats': stats, 'resultats': resultats,
    }


def decision_pour(moyenne_annuelle):
    if moyenne_annuelle is None:
        return 'non_decide'
    return 'passant' if moyenne_annuelle >= settings.SEUIL_PASSAGE else 'redoublant'


@transaction.atomic
def cloturer_annee(annee):
    """Calcule la moyenne annuelle et la décision (passant / redoublant) de chaque
    élève, puis clôture l'année. Retourne un résumé."""
    resolver = ConfigResolver()
    resume = {'passant': 0, 'redoublant': 0, 'non_decide': 0}
    for classe in annee.classes.all():
        for r in resultats_classe(classe, resolver)['resultats'].values():
            ins = r['inscription']
            ins.moyenne_annuelle = r['annuelle']
            ins.decision = decision_pour(r['annuelle'])
            ins.save(update_fields=['moyenne_annuelle', 'decision'])
            resume[ins.decision] += 1
    annee.cloturee = True
    annee.active = False
    annee.save()
    return resume
