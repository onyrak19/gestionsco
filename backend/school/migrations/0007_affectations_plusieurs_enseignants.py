"""Migration conservée pour l'historique, sans effet.

Une version intermédiaire permettait plusieurs enseignants par matière et par
classe ; cette idée a été abandonnée (voir 0008 : un seul enseignant par matière
et par classe). Ne rien modifier ici : cette migration a pu être appliquée.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0006_photo_pieces_jointes'),
    ]

    operations = [
        migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop),
    ]
