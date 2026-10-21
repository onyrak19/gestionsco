"""Niveaux scolaires (de la petite section à la terminale) et séries."""
import unicodedata

NIVEAUX = [
    'Petite section', 'Moyenne section', 'Grande section',
    'CP', 'CE1', 'CE2', 'CM1', 'CM2',
    '6ème', '5ème', '4ème', '3ème',
    'Seconde', 'Première', 'Terminale',
]
CODES_NIVEAUX = {
    'Petite section': 'PS', 'Moyenne section': 'MS', 'Grande section': 'GS',
    'CP': 'CP', 'CE1': 'CE1', 'CE2': 'CE2', 'CM1': 'CM1', 'CM2': 'CM2',
    '6ème': '6E', '5ème': '5E', '4ème': '4E', '3ème': '3E',
    'Seconde': '2NDE', 'Première': '1RE', 'Terminale': 'TLE',
}
# Niveaux pour lesquels une série est demandée
NIVEAUX_AVEC_SERIE = ('Première', 'Terminale')
SERIES = ['L', 'S', 'OSE']


def rang_niveau(niveau):
    """Position du niveau dans le cursus (0 = petite section), None si niveau libre."""
    try:
        return NIVEAUX.index(niveau)
    except ValueError:
        return None


def niveau_suivant(niveau):
    r = rang_niveau(niveau)
    if r is None or r + 1 >= len(NIVEAUX):
        return None
    return NIVEAUX[r + 1]


def lettres_majuscules(texte, longueur=3):
    """'Éducation civique' -> 'EDU' (sans accents ni espaces)."""
    sans_accent = unicodedata.normalize('NFKD', texte)
    return ''.join(c for c in sans_accent if c.isascii() and c.isalnum()).upper()[:longueur]


def construire_nom_classe(niveau, serie, numero):
    morceaux = [niveau]
    if serie:
        morceaux.append(serie)
    morceaux.append(str(numero))
    return ' '.join(morceaux)
