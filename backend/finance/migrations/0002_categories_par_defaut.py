"""Catégories de dépenses et d'entrées proposées par défaut (modifiables, on peut en ajouter)."""
from django.db import migrations

DEPENSES = [
    'Fournitures et matériel', 'Loyer', 'Électricité et eau', 'Internet et téléphone',
    'Entretien et réparations', 'Transport', 'Impôts et taxes', 'Événements et fêtes',
    'Imprévus', 'Autres dépenses',
]
ENTREES = [
    'Subvention', 'Dons et parrainage', 'Location de salle', 'Vente (livres, uniformes...)',
    'Activités et événements', 'Autres entrées',
]


def creer(apps, schema_editor):
    Categorie = apps.get_model('finance', 'CategorieFinance')
    for sens, noms in (('depense', DEPENSES), ('entree', ENTREES)):
        for nom in noms:
            Categorie.objects.get_or_create(sens=sens, nom=nom)


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(creer, migrations.RunPython.noop),
    ]
