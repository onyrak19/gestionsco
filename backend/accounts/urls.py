from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.LoginView.as_view()),
    path('inscription-enseignant/', views.InscriptionEnseignantView.as_view()),
    path('enseignants/', views.EnseignantsEnAttenteView.as_view()),
    path('enseignants/<int:pk>/', views.EnseignantUpdateView.as_view()),
    path('profile/', views.ProfileView.as_view()),
]