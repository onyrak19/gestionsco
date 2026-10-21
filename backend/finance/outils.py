"""Petits outils sans dépendance à Django (utilisables par les PDF et les tests)."""
from decimal import Decimal, ROUND_HALF_UP

MOIS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
           'septembre', 'octobre', 'novembre', 'décembre']


def mois_cle(d):
    """date -> '2026-09'"""
    return f"{d.year:04d}-{d.month:02d}"


def libelle_mois(d):
    """date -> 'Septembre 2026'"""
    return f"{MOIS_FR[d.month - 1].capitalize()} {d.year}"


def montant_fr(valeur, devise=''):
    """25000 -> '25 000 Ar' ; 1250.5 -> '1 250,50 Ar' ; None -> ''"""
    if valeur is None or valeur == '':
        return ''
    d = Decimal(str(valeur)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if d == d.to_integral_value():
        texte = f"{d:,.0f}".replace(',', ' ')
    else:
        texte = f"{d:,.2f}".replace(',', ' ').replace('.', ',')
    return f"{texte} {devise}".strip()
