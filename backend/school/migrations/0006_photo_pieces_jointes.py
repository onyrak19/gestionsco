from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import school.models
from ._outils import AddFieldSiAbsent, CreateModelSiAbsent


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('school', '0005_unicite_numero_classe'),
    ]

    operations = [
        AddFieldSiAbsent(
            model_name='eleve',
            name='photo',
            field=models.ImageField(blank=True, default='', upload_to=school.models.chemin_photo),
        ),
        CreateModelSiAbsent(
            name='PieceJointe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(blank=True, default='', max_length=120)),
                ('fichier', models.FileField(max_length=255, upload_to=school.models.chemin_piece)),
                ('nom_original', models.CharField(max_length=255)),
                ('taille', models.PositiveIntegerField(default=0)),
                ('type_mime', models.CharField(blank=True, default='', max_length=100)),
                ('date_ajout', models.DateTimeField(auto_now_add=True)),
                ('ajoute_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('inscription', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pieces', to='school.inscription')),
            ],
            options={
                'ordering': ['date_ajout', 'id'],
            },
        ),
    ]
