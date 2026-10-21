from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('journal', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activite',
            name='categorie',
            field=models.CharField(choices=[('connexion', 'Connexions'), ('note', 'Notes'), ('inscription', 'Inscriptions'), ('piece_jointe', 'Pièces jointes'), ('eleve', 'Élèves'), ('classe', 'Classes'), ('matiere', 'Matières'), ('affectation', 'Affectations'), ('annee', 'Années scolaires'), ('enseignant', 'Enseignants'), ('impression', 'Impressions'), ('etablissement', 'Établissement'), ('export', 'Exports Excel'), ('import', 'Imports Excel')], db_index=True, max_length=20),
        ),
    ]
