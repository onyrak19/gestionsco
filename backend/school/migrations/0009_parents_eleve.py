"""Parents ou tuteur de l'élève : nom et numéro de mobile (facultatifs)."""
from django.db import migrations, models

from ._outils import AddFieldSiAbsent


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0008_une_seule_affectation_par_matiere'),
    ]

    operations = [
        AddFieldSiAbsent(
            model_name='eleve',
            name='parent_nom',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        AddFieldSiAbsent(
            model_name='eleve',
            name='parent_mobile',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        AddFieldSiAbsent(
            model_name='eleve',
            name='parent2_nom',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        AddFieldSiAbsent(
            model_name='eleve',
            name='parent2_mobile',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
    ]
