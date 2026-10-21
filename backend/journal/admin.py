from django.contrib import admin

from .models import Activite


@admin.register(Activite)
class ActiviteAdmin(admin.ModelAdmin):
    """Consultation seulement : le journal ne se modifie pas."""
    list_display = ('date', 'utilisateur_nom', 'categorie', 'action', 'description')
    list_filter = ('categorie', 'action')
    search_fields = ('description', 'utilisateur_nom', 'eleve')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
