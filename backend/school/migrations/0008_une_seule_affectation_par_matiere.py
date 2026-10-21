"""Un seul enseignant par matière et par classe (pour une année).

La règle est déjà vérifiée par l'application (message clair à l'écran). Cette
migration ajoute en plus la garantie dans la base de données, SAUF s'il existe
déjà des doublons : elle ne supprime alors rien, elle affiche la liste à
corriger (écran « Affectations », rubrique « À corriger ») et laisse la base
telle quelle. `migrate` n'échoue jamais à cause de cela.
"""
from django.db import migrations
from django.db.models import Count

ANCIEN = {('enseignant', 'matiere', 'classe', 'annee_scolaire')}
NOUVEAU = {('matiere', 'classe', 'annee_scolaire')}


def appliquer_unicite(apps, schema_editor):
    Affectation = apps.get_model('school', 'Affectation')
    doublons = (
        Affectation.objects.values('matiere_id', 'classe_id', 'annee_scolaire_id')
        .annotate(n=Count('id')).filter(n__gt=1)
    )
    if doublons.exists():
        print("\n  [affectations] Plusieurs enseignants sont affectés à une même matière d'une même classe :")
        for d in doublons:
            for a in Affectation.objects.filter(
                    matiere_id=d['matiere_id'], classe_id=d['classe_id'],
                    annee_scolaire_id=d['annee_scolaire_id']).select_related('enseignant', 'matiere', 'classe'):
                print(f"    - {a.classe.nom} / {a.matiere.nom} : {a.enseignant.username}")
        print("  Retirez les doublons dans l'écran Affectations ; la contrainte en base n'a pas été ajoutée.")
        return
    try:
        schema_editor.alter_unique_together(Affectation, ANCIEN, NOUVEAU)
    except Exception as exc:   # noqa: BLE001 - base modifiée à la main : l'application garde la règle
        print(f"\n  [affectations] contrainte non ajoutée en base ({exc}) ; la règle reste vérifiée par l'application.")


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0007_affectations_plusieurs_enseignants'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterUniqueTogether(
                    name='affectation',
                    unique_together=NOUVEAU,
                ),
            ],
            database_operations=[
                migrations.RunPython(appliquer_unicite, migrations.RunPython.noop),
            ],
        ),
    ]
