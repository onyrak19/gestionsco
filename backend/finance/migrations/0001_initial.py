"""Tables du module Finances (tarifs, paiements, dépenses/entrées, salaires)."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

from school.migrations._outils import CreateModelSiAbsent


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('school', '0009_parents_eleve'),
    ]

    operations = [
        CreateModelSiAbsent(
            name='Tarif',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('niveau', models.CharField(max_length=40)),
                ('serie', models.CharField(blank=True, default='', max_length=20)),
                ('type', models.CharField(choices=[('droit', "Droit d'inscription"), ('ecolage', 'Écolage mensuel'), ('autre', 'Autre frais')], max_length=10)),
                ('libelle', models.CharField(blank=True, default='', max_length=100)),
                ('montant', models.DecimalField(decimal_places=2, max_digits=12)),
                ('annee_scolaire', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tarifs', to='school.anneescolaire')),
            ],
            options={
                'ordering': ['niveau', 'serie', 'type', 'libelle'],
                'unique_together': {('annee_scolaire', 'niveau', 'serie', 'type', 'libelle')},
            },
        ),
        CreateModelSiAbsent(
            name='CategorieFinance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100)),
                ('sens', models.CharField(choices=[('depense', 'Dépense'), ('entree', "Entrée d'argent")], max_length=10)),
                ('actif', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['sens', 'nom'],
                'verbose_name': 'catégorie',
                'unique_together': {('sens', 'nom')},
            },
        ),
        CreateModelSiAbsent(
            name='Employe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100)),
                ('prenom', models.CharField(blank=True, default='', max_length=100)),
                ('poste', models.CharField(blank=True, default='', max_length=100)),
                ('telephone', models.CharField(blank=True, default='', max_length=30)),
                ('salaire_mensuel', models.DecimalField(decimal_places=2, max_digits=12, default=0)),
                ('date_embauche', models.DateField(blank=True, null=True)),
                ('actif', models.BooleanField(default=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['nom', 'prenom'],
            },
        ),
        CreateModelSiAbsent(
            name='Paiement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(max_length=20, unique=True)),
                ('eleve_nom', models.CharField(max_length=220)),
                ('matricule', models.CharField(blank=True, default='', max_length=30)),
                ('classe_nom', models.CharField(blank=True, default='', max_length=60)),
                ('annee_libelle', models.CharField(blank=True, default='', max_length=20)),
                ('type', models.CharField(choices=[('droit', "Droit d'inscription"), ('ecolage', 'Écolage'), ('autre', 'Autre frais')], max_length=10)),
                ('date', models.DateField()),
                ('mode', models.CharField(choices=[('especes', 'Espèces'), ('mobile', 'Mobile money'), ('virement', 'Virement'), ('cheque', 'Chèque')], default='especes', max_length=10)),
                ('reference', models.CharField(blank=True, default='', max_length=100)),
                ('observation', models.CharField(blank=True, default='', max_length=255)),
                ('montant_total', models.DecimalField(decimal_places=2, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('annule', models.BooleanField(db_index=True, default=False)),
                ('motif_annulation', models.CharField(blank=True, default='', max_length=255)),
                ('annule_le', models.DateTimeField(blank=True, null=True)),
                ('annee_scolaire', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paiements', to='school.anneescolaire')),
                ('annule_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('inscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paiements', to='school.inscription')),
                ('saisi_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date', '-id'],
            },
        ),
        CreateModelSiAbsent(
            name='LignePaiement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('libelle', models.CharField(max_length=150)),
                ('mois', models.DateField(blank=True, null=True)),
                ('montant', models.DecimalField(decimal_places=2, max_digits=12)),
                ('paiement', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='finance.paiement')),
                ('tarif', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='finance.tarif')),
            ],
            options={
                'ordering': ['mois', 'id'],
            },
        ),
        CreateModelSiAbsent(
            name='Mouvement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(db_index=True)),
                ('libelle', models.CharField(max_length=200)),
                ('montant', models.DecimalField(decimal_places=2, max_digits=12)),
                ('imprevu', models.BooleanField(default=False)),
                ('reference', models.CharField(blank=True, default='', max_length=100)),
                ('notes', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('categorie', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mouvements', to='finance.categoriefinance')),
                ('saisi_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date', '-id'],
            },
        ),
        CreateModelSiAbsent(
            name='AvanceSalaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('montant', models.DecimalField(decimal_places=2, max_digits=12)),
                ('motif', models.CharField(blank=True, default='', max_length=255)),
                ('annulee', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='avances', to='finance.employe')),
                ('saisi_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date', '-id'],
            },
        ),
        CreateModelSiAbsent(
            name='PaieSalaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero', models.CharField(max_length=20, unique=True)),
                ('employe_nom', models.CharField(max_length=220)),
                ('poste', models.CharField(blank=True, default='', max_length=100)),
                ('date', models.DateField(db_index=True)),
                ('mode', models.CharField(choices=[('especes', 'Espèces'), ('mobile', 'Mobile money'), ('virement', 'Virement'), ('cheque', 'Chèque')], default='especes', max_length=10)),
                ('salaire_mensuel', models.DecimalField(decimal_places=2, max_digits=12, default=0)),
                ('montant_brut', models.DecimalField(decimal_places=2, max_digits=12)),
                ('retenue_avances', models.DecimalField(decimal_places=2, max_digits=12, default=0)),
                ('autres_retenues', models.DecimalField(decimal_places=2, max_digits=12, default=0)),
                ('motif_retenues', models.CharField(blank=True, default='', max_length=255)),
                ('net_paye', models.DecimalField(decimal_places=2, max_digits=12)),
                ('exceptionnel', models.BooleanField(default=False)),
                ('motif_exceptionnel', models.CharField(blank=True, default='', max_length=255)),
                ('observation', models.CharField(blank=True, default='', max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('annule', models.BooleanField(db_index=True, default=False)),
                ('motif_annulation', models.CharField(blank=True, default='', max_length=255)),
                ('annule_le', models.DateTimeField(blank=True, null=True)),
                ('annule_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='paies', to='finance.employe')),
                ('saisi_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date', '-id'],
            },
        ),
        CreateModelSiAbsent(
            name='LignePaie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mois', models.DateField()),
                ('montant', models.DecimalField(decimal_places=2, max_digits=12, default=0)),
                ('paie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='finance.paiesalaire')),
            ],
            options={
                'ordering': ['mois', 'id'],
            },
        ),
        CreateModelSiAbsent(
            name='RetenueAvance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('montant', models.DecimalField(decimal_places=2, max_digits=12)),
                ('avance', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='retenues', to='finance.avancesalaire')),
                ('paie', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='retenues', to='finance.paiesalaire')),
            ],
        ),
    ]
