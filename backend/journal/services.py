"""Écriture dans le journal d'activité.

`enregistrer` ne lève jamais d'exception : un incident d'écriture dans le
journal ne doit pas empêcher une saisie de notes ou une inscription.
"""
import logging
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction

from .models import Activite

logger = logging.getLogger(__name__)

ROLES = {'admin': 'Administrateur', 'enseignant': 'Enseignant'}


def nom_complet(user):
    if user is None or not getattr(user, 'pk', None):
        return ''
    complet = (user.get_full_name() or '').strip()
    return complet or user.username


def role_de(user):
    profil = getattr(user, 'profile', None)
    return getattr(profil, 'role', '') or ''


def acteur(user):
    """« Enseignant Jean Martin » : sujet des phrases du journal."""
    if user is None or not getattr(user, 'pk', None):
        return "Un visiteur"
    role = ROLES.get(role_de(user), 'Utilisateur')
    return f"{role} {nom_complet(user)}"


def _adresse_ip(request):
    meta = getattr(request, 'META', None) or {}
    return meta.get('REMOTE_ADDR') or None


def enregistrer(request, categorie, action, description, *, utilisateur=None,
                annee='', classe='', matiere='', eleve='', cible_id=None):
    """Ajoute une ligne au journal. `request` peut être None."""
    user = utilisateur if utilisateur is not None else getattr(request, 'user', None)
    if user is not None and not getattr(user, 'pk', None):
        user = None
    try:
        with transaction.atomic():   # point de sauvegarde : n'affecte pas l'opération en cours
            Activite.objects.create(
                utilisateur=user,
                utilisateur_nom=nom_complet(user)[:150],
                utilisateur_role=role_de(user)[:20],
                categorie=categorie,
                action=action,
                description=description,
                annee=str(annee or '')[:20],
                classe=str(classe or '')[:60],
                matiere=str(matiere or '')[:100],
                eleve=str(eleve or '')[:220],
                cible_id=cible_id if isinstance(cible_id, int) and cible_id >= 0 else None,
                adresse_ip=_adresse_ip(request),
            )
    except Exception:   # noqa: BLE001 - voir la docstring du module
        logger.exception("Impossible d'enregistrer l'activité dans le journal.")


# ---------------------------------------------------------------------------
# Mise en forme des valeurs pour les descriptions
# ---------------------------------------------------------------------------
def valeur_lisible(valeur):
    if valeur is None or valeur == '':
        return '(vide)'
    if isinstance(valeur, bool):
        return 'oui' if valeur else 'non'
    if isinstance(valeur, datetime):
        return valeur.strftime('%d/%m/%Y %H:%M')
    if isinstance(valeur, date):
        return valeur.strftime('%d/%m/%Y')
    if isinstance(valeur, (Decimal, float)):
        texte = format(Decimal(str(valeur)).normalize(), 'f')
        return texte.replace('.', ',')
    return str(valeur)


def difference(avant, apres, libelles):
    """« coefficient : 1 → 2 ; nom : A → B » pour les seuls champs modifiés.

    avant / apres : {champ: valeur} ; libelles : {champ: texte affiché}."""
    morceaux = []
    for champ, libelle in libelles.items():
        ancien, nouveau = avant.get(champ), apres.get(champ)
        if valeur_lisible(ancien) != valeur_lisible(nouveau):
            morceaux.append(f"{libelle} : {valeur_lisible(ancien)} → {valeur_lisible(nouveau)}")
    return ' ; '.join(morceaux)
