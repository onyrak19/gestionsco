from django.urls import path

from . import views

urlpatterns = [
    path('parametres/', views.ParametresView.as_view()),
    path('impressions/', views.ImpressionsView.as_view()),

    # Tarifs (droits, écolages, autres frais) par niveau
    path('tarifs/', views.TarifsView.as_view()),
    path('tarifs/copier/', views.TarifsCopierView.as_view()),

    # Encaissements des élèves
    path('situations/', views.SituationsView.as_view()),
    path('inscriptions/<int:pk>/situation/', views.SituationEleveView.as_view()),
    path('paiements/', views.PaiementListCreateView.as_view()),
    path('paiements/<int:pk>/', views.PaiementDetailView.as_view()),
    path('paiements/<int:pk>/annuler/', views.PaiementAnnulerView.as_view()),
    path('paiements/<int:pk>/recu/', views.PaiementRecuView.as_view()),

    # Dépenses et entrées d'argent
    path('categories/', views.CategorieListView.as_view()),
    path('categories/<int:pk>/', views.CategorieDetailView.as_view()),
    path('mouvements/', views.MouvementListView.as_view()),
    path('mouvements/<int:pk>/', views.MouvementDetailView.as_view()),

    # Salaires
    path('employes/', views.EmployeListView.as_view()),
    path('employes/<int:pk>/', views.EmployeDetailView.as_view()),
    path('employes/<int:pk>/situation/', views.EmployeSituationView.as_view()),
    path('avances/', views.AvanceListView.as_view()),
    path('avances/<int:pk>/annuler/', views.AvanceAnnulerView.as_view()),
    path('salaires/', views.SalaireListCreateView.as_view()),
    path('salaires/groupe/', views.SalaireGroupeView.as_view()),
    path('salaires/<int:pk>/', views.SalaireDetailView.as_view()),
    path('salaires/<int:pk>/annuler/', views.SalaireAnnulerView.as_view()),
    path('salaires/<int:pk>/fiche/', views.SalaireFicheView.as_view()),

    # Bilan et impressions
    path('bilan/', views.BilanView.as_view()),
    path('pdf/cartes-ecolage/', views.PdfCartesEcolageView.as_view()),
    path('pdf/impayes/', views.PdfImpayesView.as_view()),
    path('pdf/rapport/', views.PdfRapportView.as_view()),
    path('pdf/etat-salaires/', views.PdfEtatSalairesView.as_view()),
]
