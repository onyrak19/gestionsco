from django.db import migrations

from ._outils import UniqueTogetherSiAbsent


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0004_donnees_existantes'),
    ]

    operations = [
        UniqueTogetherSiAbsent(
            name='inscription',
            unique_together={('eleve', 'annee_scolaire'), ('classe', 'numero')},
        ),
    ]
