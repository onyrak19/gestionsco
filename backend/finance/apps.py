from django.apps import AppConfig


class FinanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finance'
    verbose_name = 'Finances'

    def ready(self):
        # Ajoute les données financières à l'écran Import / Export
        from . import jeux
        jeux.enregistrer()
