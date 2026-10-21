"""Résolution sûre des fichiers de l'interface compilée (sans dépendance à Django)."""
from pathlib import Path


def resoudre(racine, chemin):
    """Fichier `chemin` situé dans `racine`, ou None s'il n'existe pas ou s'il
    sort du dossier (ex. « ../../secret »)."""
    if not chemin:
        return None
    racine = Path(racine).resolve()
    try:
        candidat = (racine / chemin).resolve()
        candidat.relative_to(racine)
    except (ValueError, OSError):
        return None
    return candidat if candidat.is_file() else None
