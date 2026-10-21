from django.contrib import admin
from .models import (
    AnneeScolaire, Classe, Matiere, Eleve,
    Inscription, Affectation, Note, PieceJointe,
)

for model in [AnneeScolaire, Classe, Matiere, Eleve, Inscription, Affectation, Note, PieceJointe]:
    admin.site.register(model)
