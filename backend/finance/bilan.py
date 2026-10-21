"""Bilan financier d'une période : entrées, dépenses, imprévus, salaires, solde.

Comptabilité de caisse : une opération compte à sa date.
* Entrées  : paiements des élèves (hors annulés) + entrées d'argent saisies.
* Dépenses : dépenses saisies (dont imprévus) + salaires nets payés + avances données.
  (Une avance sort de la caisse le jour où elle est donnée ; la retenue qui la rembourse
  réduit ensuite le net de la paie, sans double comptage.)
"""
from collections import defaultdict
from decimal import Decimal

from .models import AvanceSalaire, Mouvement, Paiement, PaieSalaire
from .services import ZERO, libelle_mois, num, premier_du_mois

TYPES_LIBELLES = dict(Paiement.TYPES)


def _somme(valeurs):
    return sum(valeurs, ZERO)


def bilan(debut, fin):
    plage = (debut, fin)
    paiements = list(Paiement.objects.filter(annule=False, date__range=plage))
    mouvements = list(Mouvement.objects.filter(date__range=plage).select_related('categorie'))
    paies = list(PaieSalaire.objects.filter(annule=False, date__range=plage))
    avances = list(AvanceSalaire.objects.filter(annulee=False, date__range=plage))

    scolarite = {t: ZERO for t in TYPES_LIBELLES}
    for p in paiements:
        scolarite[p.type] += p.montant_total
    total_scolarite = _somme(scolarite.values())

    entrees_cat, depenses_cat = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    imprevus, nb_imprevus = ZERO, 0
    for m in mouvements:
        if m.categorie.sens == 'entree':
            entrees_cat[m.categorie.nom] += m.montant
        else:
            depenses_cat[m.categorie.nom] += m.montant
            if m.imprevu:
                imprevus += m.montant
                nb_imprevus += 1
    total_entrees_diverses = _somme(entrees_cat.values())
    total_fonctionnement = _somme(depenses_cat.values())
    total_salaires = _somme(p.net_paye for p in paies)
    total_avances = _somme(a.montant for a in avances)

    total_entrees = total_scolarite + total_entrees_diverses
    total_depenses = total_fonctionnement + total_salaires + total_avances

    # Évolution mois par mois
    par_mois = defaultdict(lambda: {'entrees': ZERO, 'depenses': ZERO})
    for p in paiements:
        par_mois[premier_du_mois(p.date)]['entrees'] += p.montant_total
    for m in mouvements:
        cle = 'entrees' if m.categorie.sens == 'entree' else 'depenses'
        par_mois[premier_du_mois(m.date)][cle] += m.montant
    for p in paies:
        par_mois[premier_du_mois(p.date)]['depenses'] += p.net_paye
    for a in avances:
        par_mois[premier_du_mois(a.date)]['depenses'] += a.montant

    return {
        'periode': {'debut': debut.isoformat(), 'fin': fin.isoformat()},
        'entrees': {
            'total': num(total_entrees),
            'scolarite': {**{t: num(v) for t, v in scolarite.items()}, 'total': num(total_scolarite)},
            'autres': [{'categorie': n, 'total': num(v)} for n, v in sorted(entrees_cat.items())],
            'total_autres': num(total_entrees_diverses),
        },
        'depenses': {
            'total': num(total_depenses),
            'categories': [{'categorie': n, 'total': num(v)} for n, v in sorted(depenses_cat.items())],
            'total_fonctionnement': num(total_fonctionnement),
            'imprevus': num(imprevus), 'nb_imprevus': nb_imprevus,
            'salaires': num(total_salaires), 'avances': num(total_avances),
            'total_salaires': num(total_salaires + total_avances),
        },
        'solde': num(total_entrees - total_depenses),
        'par_mois': [
            {'mois': f"{m.year:04d}-{m.month:02d}", 'libelle': libelle_mois(m),
             'entrees': num(v['entrees']), 'depenses': num(v['depenses']),
             'solde': num(v['entrees'] - v['depenses'])}
            for m, v in sorted(par_mois.items())
        ],
    }


def journal_caisse(debut, fin):
    """Toutes les opérations de la période, dans l'ordre : [(date, nature, libellé, référence, entrée, sortie)]."""
    plage = (debut, fin)
    lignes = []
    for p in Paiement.objects.filter(annule=False, date__range=plage).prefetch_related('lignes'):
        detail = ', '.join(l.libelle for l in p.lignes.all())
        lignes.append((p.date, p.id, 'Scolarité', f"{p.eleve_nom} ({p.classe_nom}) — {detail}", p.numero,
                       p.montant_total, None))
    for m in Mouvement.objects.filter(date__range=plage).select_related('categorie'):
        entree = m.categorie.sens == 'entree'
        nature = ('Entrée' if entree else ('Imprévu' if m.imprevu else 'Dépense')) + f" — {m.categorie.nom}"
        lignes.append((m.date, m.id, nature, m.libelle, m.reference,
                       m.montant if entree else None, None if entree else m.montant))
    for p in PaieSalaire.objects.filter(annule=False, date__range=plage):
        lignes.append((p.date, p.id, 'Salaire', f"{p.employe_nom}", p.numero, None, p.net_paye))
    for a in AvanceSalaire.objects.filter(annulee=False, date__range=plage).select_related('employe'):
        lignes.append((a.date, a.id, 'Avance sur salaire', f"{a.employe.nom_complet} {a.motif}".strip(), '',
                       None, a.montant))
    lignes.sort(key=lambda l: (l[0], l[2], l[1]))
    return lignes
