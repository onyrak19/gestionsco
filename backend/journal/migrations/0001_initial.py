from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

from school.migrations._outils import CreateModelSiAbsent


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        CreateModelSiAbsent(
            name='Activite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('utilisateur_nom', models.CharField(blank=True, max_length=150)),
                ('utilisateur_role', models.CharField(blank=True, max_length=20)),
                ('categorie', models.CharField(choices=[('connexion', 'Connexions'), ('note', 'Notes'), ('inscription', 'Inscriptions'), ('piece_jointe', 'Pièces jointes'), ('eleve', 'Élèves'), ('classe', 'Classes'), ('matiere', 'Matières'), ('affectation', 'Affectations'), ('annee', 'Années scolaires'), ('enseignant', 'Enseignants'), ('impression', 'Impressions'), ('etablissement', 'Établissement')], db_index=True, max_length=20)),
                ('action', models.CharField(choices=[('creation', 'Création'), ('modification', 'Modification'), ('suppression', 'Suppression'), ('connexion', 'Connexion'), ('echec', 'Échec'), ('impression', 'Impression'), ('cloture', 'Clôture'), ('validation', 'Validation')], db_index=True, max_length=20)),
                ('description', models.TextField()),
                ('annee', models.CharField(blank=True, db_index=True, default='', max_length=20)),
                ('classe', models.CharField(blank=True, default='', max_length=60)),
                ('matiere', models.CharField(blank=True, default='', max_length=100)),
                ('eleve', models.CharField(blank=True, default='', max_length=220)),
                ('cible_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('adresse_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('utilisateur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'activité',
                'verbose_name_plural': 'activités',
                'ordering': ['-date', '-id'],
            },
        ),
    ]
