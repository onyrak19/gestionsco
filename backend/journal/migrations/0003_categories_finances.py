from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('journal', '0002_categories_export_import'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activite',
            name='categorie',
            field=models.CharField(choices=[('connexion', 'Connexions'), ('note', 'Notes'), ('inscription', 'Inscriptions'), ('piece_jointe', 'Pièces jointes'), ('eleve', 'Élèves'), ('classe', 'Classes'), ('matiere', 'Matières'), ('affectation', 'Affectations'), ('annee', 'Années scolaires'), ('enseignant', 'Enseignants'), ('impression', 'Impressions'), ('etablissement', 'Établissement'), ('export', 'Exports Excel'), ('import', 'Imports Excel'), ('paiement', 'Paiements des élèves'), ('finance', 'Finances (dépenses, entrées, tarifs)'), ('salaire', 'Salaires et avances')], db_index=True, max_length=20),
        ),
    ]
