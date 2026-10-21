from django.contrib import admin

from .models import CategorieFinance, Employe, Mouvement, Paiement, PaieSalaire, Tarif

admin.site.register(Tarif)
admin.site.register(CategorieFinance)
admin.site.register(Mouvement)
admin.site.register(Employe)


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ('numero', 'date', 'eleve_nom', 'type', 'montant_total', 'annule')
    list_filter = ('type', 'annule')
    search_fields = ('numero', 'eleve_nom', 'matricule')


@admin.register(PaieSalaire)
class PaieSalaireAdmin(admin.ModelAdmin):
    list_display = ('numero', 'date', 'employe_nom', 'montant_brut', 'net_paye', 'annule')
    list_filter = ('annule',)
    search_fields = ('numero', 'employe_nom')
