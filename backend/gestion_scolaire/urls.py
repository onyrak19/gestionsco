from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include, re_path

from accounts.tokens import StatutTokenRefreshView

from .frontend import servir_frontend


def ping(request):
    """Permet à Trouver_Serveur.exe de reconnaître CE serveur sur le réseau."""
    return HttpResponse('ECOLE', content_type='text/plain')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/ping/', ping),
    path('api/auth/', include('accounts.urls')),
    path('api/school/', include('school.urls')),
    path('api/journal/', include('journal.urls')),
    path('api/finance/', include('finance.urls')),
    path('api/token/refresh/', StatutTokenRefreshView.as_view()),
    # Tout le reste : l'interface React (sauf /api, /admin et /django-static)
    re_path(r'^(?!api/|admin/|django-static/)(?P<chemin>.*)$', servir_frontend),
]