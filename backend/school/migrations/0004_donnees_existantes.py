import unicodedata

from django.db import migrations


def _lettres(texte, longueur=3):
    sans_accent = unicodedata.normalize('NFKD', texte)
    return ''.join(c for c in sans_accent if c.isascii() and c.isalnum()).upper()[:longueur]


def remplir(apps, schema_editor):
    """Met à niveau les données déjà présentes :
    - numéro d'ordre des inscriptions existantes, classe par classe (ordre d'inscription) ;
    - code automatique des matières qui n'en ont pas ;
    - valeurs vides ('') des codes remplacées par NULL.
    """
    Inscription = apps.get_model('school', 'Inscription')
    Matiere = apps.get_model('school', 'Matiere')

    dernier = {}
    for ins in Inscription.objects.order_by('classe_id', 'id'):
        dernier[ins.classe_id] = dernier.get(ins.classe_id, 0) + 1
        ins.numero = dernier[ins.classe_id]
        ins.save(update_fields=['numero'])

    Matiere.objects.filter(code='').update(code=None)
    pris = set(Matiere.objects.exclude(code__isnull=True).values_list('code', flat=True))
    for m in Matiere.objects.filter(code__isnull=True).order_by('id'):
        base = _lettres(m.nom) or 'MAT'
        code, i = base, 2
        while code in pris:
            code = f"{base}{i}"
            i += 1
        pris.add(code)
        m.code = code
        m.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0003_evolutions_scolaires'),
    ]

    operations = [
        migrations.RunPython(remplir, migrations.RunPython.noop),
    ]
