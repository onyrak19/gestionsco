from django.db import migrations


def creer_profils_superusers(apps, schema_editor):
    """Donne un profil administrateur aux superusers existants qui n'en ont
    pas (créés avec `createsuperuser` avant l'ajout du signal)."""
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('accounts', 'UserProfile')
    for user in User.objects.filter(is_superuser=True, profile__isnull=True):
        UserProfile.objects.create(user=user, role='admin', statut='valide')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(creer_profils_superusers, migrations.RunPython.noop),
    ]
