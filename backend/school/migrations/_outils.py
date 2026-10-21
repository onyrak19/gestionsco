"""Opérations de migration « réexécutables ».

MySQL ne peut pas annuler les modifications de structure (pas de DDL
transactionnel) : si une migration échoue en cours de route, les premières
opérations restent appliquées et un nouveau `migrate` plantait sur « colonne
déjà existante » / « table déjà existante ». Ces variantes ignorent ce qui
existe déjà, ce qui permet de simplement relancer `python manage.py migrate`.
(Le fichier commence par « _ » : Django ne le prend pas pour une migration.)
"""
from django.db import migrations


def _colonnes(schema_editor, table):
    connexion = schema_editor.connection
    with connexion.cursor() as curseur:
        return {c.name for c in connexion.introspection.get_table_description(curseur, table)}


class CreateModelSiAbsent(migrations.CreateModel):
    """Crée la table seulement si elle n'existe pas encore."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        modele = to_state.apps.get_model(app_label, self.name)
        if modele._meta.db_table in schema_editor.connection.introspection.table_names():
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class AddFieldSiAbsent(migrations.AddField):
    """Ajoute la colonne seulement si elle n'existe pas encore."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        modele = to_state.apps.get_model(app_label, self.model_name)
        champ = modele._meta.get_field(self.name)
        if champ.column in _colonnes(schema_editor, modele._meta.db_table):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)


class UniqueTogetherSiAbsent(migrations.AlterUniqueTogether):
    """Pose la contrainte d'unicité seulement si elle n'existe pas encore."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        modele = to_state.apps.get_model(app_label, self.name)
        connexion = schema_editor.connection
        with connexion.cursor() as curseur:
            existantes = connexion.introspection.get_constraints(curseur, modele._meta.db_table)
        colonnes_voulues = [
            [modele._meta.get_field(nom).column for nom in groupe]
            for groupe in (self.unique_together or [])
        ]
        deja = [
            infos['columns'] for infos in existantes.values()
            if infos.get('unique') and not infos.get('primary_key')
        ]
        if all(cols in deja for cols in colonnes_voulues):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)
