"""Photos d'élèves et pièces jointes : validation et traitement des fichiers.

Ce module ne dépend pas de Django (seulement de Pillow) pour rester simple à
tester. Les erreurs sont des `ValueError` dont le message est affichable tel quel.
"""
import mimetypes
import os
from io import BytesIO

from PIL import Image, ImageOps

# ---- Photo
TAILLE_MAX_PHOTO = 8 * 1024 * 1024        # 8 Mo avant réduction
DIMENSION_PHOTO = 480                      # côté le plus long, en pixels
FORMATS_PHOTO = {'JPEG', 'PNG', 'WEBP'}

# ---- Pièces jointes
TAILLE_MAX_PIECE = 10 * 1024 * 1024       # 10 Mo par fichier
NB_MAX_PIECES = 10                         # par envoi

# extension -> (début attendu du fichier, type MIME)
TYPES_PIECES = {
    '.pdf': (b'%PDF', 'application/pdf'),
    '.jpg': (b'\xff\xd8\xff', 'image/jpeg'),
    '.jpeg': (b'\xff\xd8\xff', 'image/jpeg'),
    '.png': (b'\x89PNG\r\n\x1a\n', 'image/png'),
    '.webp': (b'RIFF', 'image/webp'),
    '.docx': (b'PK', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    '.xlsx': (b'PK', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    '.odt': (b'PK', 'application/vnd.oasis.opendocument.text'),
    '.doc': (b'\xd0\xcf\x11\xe0', 'application/msword'),
    '.xls': (b'\xd0\xcf\x11\xe0', 'application/vnd.ms-excel'),
}
EXTENSIONS_AFFICHEES = 'PDF, JPG, PNG, WebP, Word, Excel ou ODT'


def traiter_photo(fichier):
    """Lit une photo envoyée, la corrige (rotation), la réduit et la renvoie en
    octets JPEG. Lève ValueError si ce n'est pas une image acceptable."""
    donnees = fichier.read(TAILLE_MAX_PHOTO + 1)
    if len(donnees) > TAILLE_MAX_PHOTO:
        raise ValueError("La photo dépasse 8 Mo : choisissez une image plus légère.")
    if not donnees:
        raise ValueError("Le fichier de la photo est vide.")
    try:
        image = Image.open(BytesIO(donnees))
        format_image = image.format
        image.load()   # décode tout : détecte les fichiers tronqués ou piégés
    except Exception:   # noqa: BLE001 - Pillow lève des erreurs variées
        raise ValueError("Ce fichier n'est pas une image valide (JPG, PNG ou WebP).")
    if format_image not in FORMATS_PHOTO:
        raise ValueError("Format de photo non pris en charge : utilisez JPG, PNG ou WebP.")

    image = ImageOps.exif_transpose(image)   # photos de téléphone : bon sens de lecture
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        rgba = image.convert('RGBA')
        fond = Image.new('RGB', rgba.size, (255, 255, 255))
        fond.paste(rgba, mask=rgba.split()[-1])
        image = fond
    else:
        image = image.convert('RGB')
    image.thumbnail((DIMENSION_PHOTO, DIMENSION_PHOTO))

    sortie = BytesIO()
    image.save(sortie, 'JPEG', quality=85, optimize=True)
    return sortie.getvalue()


def valider_piece(nom, debut, taille):
    """Contrôle une pièce jointe (nom d'origine, premiers octets, taille).
    Retourne (extension, type MIME). Lève ValueError si elle est refusée."""
    nom_court = os.path.basename(nom or '')
    extension = os.path.splitext(nom_court)[1].lower()
    if extension not in TYPES_PIECES:
        raise ValueError(
            f"« {nom_court} » : type de fichier non accepté. Formats possibles : {EXTENSIONS_AFFICHEES}.")
    if taille <= 0:
        raise ValueError(f"« {nom_court} » est vide.")
    if taille > TAILLE_MAX_PIECE:
        raise ValueError(f"« {nom_court} » dépasse 10 Mo.")
    attendu, type_mime = TYPES_PIECES[extension]
    if not debut.startswith(attendu) or (extension == '.webp' and debut[8:12] != b'WEBP'):
        raise ValueError(f"« {nom_court} » : le contenu ne correspond pas au format {extension}.")
    return extension, type_mime


def type_mime_de(nom_fichier):
    return mimetypes.guess_type(nom_fichier)[0] or 'application/octet-stream'
