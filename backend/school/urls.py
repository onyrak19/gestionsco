from django.urls import path
from . import views, views_excel

urlpatterns = [
    path('export/catalogue/', views_excel.ExportCatalogueView.as_view()),
    path('export/', views_excel.ExportView.as_view()),
    path('import/jeux/', views_excel.ImportJeuxView.as_view()),
    path('import/modele/<str:cle>/', views_excel.ImportModeleView.as_view()),
    path('import/', views_excel.ImportView.as_view()),
    path('etablissement/', views.EtablissementView.as_view()),
    path('niveaux/', views.NiveauxView.as_view()),

    path('annees/', views.AnneeScolaireListView.as_view()),
    path('annees/active/', views.AnneeActiveView.as_view()),
    path('annees/<int:pk>/', views.AnneeScolaireDetailView.as_view()),
    path('annees/<int:pk>/cloturer/', views.AnneeCloturerView.as_view()),

    path('classes/', views.ClasseListView.as_view()),
    path('classes/<int:pk>/', views.ClasseDetailView.as_view()),
    path('classes/<int:pk>/releve/', views.ReleveClasseView.as_view()),
    path('config-matieres/', views.ConfigMatieresView.as_view()),

    path('matieres/', views.MatiereListView.as_view()),
    path('matieres/<int:pk>/', views.MatiereDetailView.as_view()),

    path('eleves/', views.EleveListView.as_view()),
    path('eleves/<int:pk>/', views.EleveDetailView.as_view()),
    path('eleves/<int:pk>/dossier/', views.EleveDossierView.as_view()),
    path('eleves/<int:pk>/photo/', views.ElevePhotoView.as_view()),

    path('inscriptions/', views.InscriptionListView.as_view()),
    path('inscriptions/<int:pk>/', views.InscriptionDetailView.as_view()),
    path('inscriptions/<int:pk>/decision/', views.InscriptionDecisionView.as_view()),
    path('inscriptions/<int:pk>/pieces/', views.InscriptionPiecesView.as_view()),
    path('pieces-jointes/<int:pk>/', views.PieceJointeView.as_view()),

    path('affectations/', views.AffectationListView.as_view()),
    path('affectations/mes/', views.MesAffectationsView.as_view()),
    path('affectations/<int:pk>/', views.AffectationDetailView.as_view()),

    path('notes/', views.NoteListView.as_view()),
    path('notes/upsert/', views.NoteUpsertView.as_view()),
    path('notes/moyennes/<int:eleve_id>/', views.MoyennesEleveView.as_view()),

    path('pdf/cartes/', views.PdfCartesView.as_view()),
    path('pdf/bulletins/', views.PdfBulletinsView.as_view()),
    path('pdf/certificats/', views.PdfCertificatsView.as_view()),
    path('pdf/fiches-appel/', views.PdfFichesAppelView.as_view()),
]
