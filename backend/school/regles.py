"""Règles d'inscription : passage en classe supérieure, redoublement."""
from rest_framework import serializers

from .models import Inscription
from .niveaux import NIVEAUX, NIVEAUX_AVEC_SERIE, niveau_suivant, rang_niveau


def verifier_admissibilite(eleve, classe):
    """Vérifie qu'un élève peut s'inscrire dans `classe` d'après son parcours.

    - nouvel élève : libre ;
    - « passant » : doit aller dans le niveau juste au-dessus (et garder sa série
      en passant de Première à Terminale) ;
    - « redoublant » : doit être réinscrit dans le même niveau ;
    - l'année précédente doit être clôturée pour connaître la décision.
    """
    annee = classe.annee_scolaire
    precedente = (
        Inscription.objects.filter(
            eleve=eleve, annee_scolaire__date_debut__lt=annee.date_debut
        ).select_related('classe', 'annee_scolaire')
        .order_by('-annee_scolaire__date_debut').first()
    )
    if precedente is None:
        return

    lib = precedente.annee_scolaire.libelle
    if not precedente.annee_scolaire.cloturee:
        raise serializers.ValidationError(
            f"L'année {lib} de cet élève n'est pas clôturée : clôturez-la pour "
            f"connaître sa décision (passant / redoublant)."
        )

    ancien, nouveau = precedente.classe.niveau, classe.niveau
    if rang_niveau(ancien) is None or rang_niveau(nouveau) is None:
        return  # niveaux libres : pas de règle automatique

    decision = precedente.decision
    if decision == 'non_decide':
        raise serializers.ValidationError(
            f"Aucune décision pour {ancien} en {lib} (pas de notes). Ouvrez le dossier "
            f"de l'élève et indiquez s'il est passant ou redoublant."
        )
    if decision == 'passant':
        suivant = niveau_suivant(ancien)
        if suivant is None:
            raise serializers.ValidationError(
                f"Cet élève a terminé le cycle ({NIVEAUX[-1]}) : il ne peut plus être inscrit."
            )
        if nouveau != suivant:
            raise serializers.ValidationError(
                f"Élève passant en {ancien} ({lib}) : il doit être inscrit en {suivant}, pas en {nouveau}."
            )
        if (ancien in NIVEAUX_AVEC_SERIE and nouveau in NIVEAUX_AVEC_SERIE
                and precedente.classe.serie != classe.serie):
            raise serializers.ValidationError(
                f"Élève de la série {precedente.classe.serie or '—'} : il doit rester "
                f"dans la même série en {nouveau}."
            )
    elif decision == 'redoublant':
        if nouveau != ancien:
            raise serializers.ValidationError(
                f"Élève redoublant en {ancien} ({lib}) : il doit être réinscrit en {ancien}, pas en {nouveau}."
            )
        if ancien in NIVEAUX_AVEC_SERIE and precedente.classe.serie != classe.serie:
            raise serializers.ValidationError(
                f"Élève redoublant : il doit rester dans la série {precedente.classe.serie or '—'}."
            )
    else:  # en_cours alors que l'année est clôturée : cas anormal
        raise serializers.ValidationError(
            f"La décision de l'année {lib} n'est pas définie pour cet élève."
        )
