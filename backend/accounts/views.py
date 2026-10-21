from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.models import update_last_login
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from journal import services as journal

from .authentication import message_blocage
from .models import UserProfile
from .permissions import IsAdminRole
from .serializers import (
    InscriptionEnseignantSerializer, UserSerializer, UserUpdateSerializer,
)


class LoginView(generics.GenericAPIView):
    # authentication_classes vide : un ancien token expiré présent dans le
    # navigateur ne doit pas empêcher de se reconnecter.
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': "Nom d'utilisateur et mot de passe requis."},
                            status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request=request, username=username, password=password)
        if user is None:
            # On ne recopie jamais l'identifiant saisi (il peut contenir un mot de passe tapé par erreur)
            connu = User.objects.filter(username=username).first() if isinstance(username, str) else None
            if connu:
                journal.enregistrer(
                    request, 'connexion', 'echec',
                    f"Échec de connexion : mauvais mot de passe pour {journal.nom_complet(connu)}.",
                    utilisateur=connu)
            else:
                journal.enregistrer(request, 'connexion', 'echec',
                                    "Tentative de connexion avec un identifiant inconnu.")
            return Response({'error': 'Identifiants invalides'},
                            status=status.HTTP_401_UNAUTHORIZED)

        # Profil manquant, enseignant en attente / refusé / désactivé
        message = message_blocage(user)
        if message:
            journal.enregistrer(
                request, 'connexion', 'echec',
                f"Connexion refusée pour {journal.nom_complet(user)} : {message}", utilisateur=user)
            return Response({'error': message}, status=status.HTTP_403_FORBIDDEN)

        update_last_login(None, user)
        journal.enregistrer(request, 'connexion', 'connexion',
                            f"{journal.acteur(user)} s'est connecté.", utilisateur=user)
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data,
        })


class InscriptionEnseignantView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = InscriptionEnseignantSerializer
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'inscription'

    def perform_create(self, serializer):
        user = serializer.save()
        journal.enregistrer(
            self.request, 'enseignant', 'creation',
            f"{journal.nom_complet(user)} a demandé un compte enseignant (en attente de validation).",
            utilisateur=user, cible_id=user.pk)


class EnseignantsEnAttenteView(generics.ListAPIView):
    """Liste des enseignants, filtrée par statut (?statut=en_attente par défaut)."""
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        statut = self.request.query_params.get('statut', 'en_attente')
        return User.objects.filter(
            profile__role='enseignant',
            profile__statut=statut,
        ).select_related('profile').order_by('-id')


class EnseignantUpdateView(generics.RetrieveUpdateAPIView):
    """Modification de l'email / du statut d'un ENSEIGNANT uniquement
    (un compte administrateur ne peut pas être modifié par ce endpoint)."""
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return User.objects.filter(profile__role='enseignant').select_related('profile')

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UserUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        ancien_statut, ancien_email = instance.profile.statut, instance.email
        serializer = UserUpdateSerializer(
            instance, data=request.data, partial=kwargs.pop('partial', False)
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        self._journaliser(request, instance, ancien_statut, ancien_email)
        return Response(UserSerializer(instance).data)

    @staticmethod
    def _journaliser(request, instance, ancien_statut, ancien_email):
        qui, cible = journal.acteur(request.user), journal.nom_complet(instance)
        nouveau = instance.profile.statut
        if nouveau != ancien_statut:
            phrases = {
                'valide': ("validation", f"a validé le compte de l'enseignant {cible}"
                           if ancien_statut == 'en_attente'
                           else f"a réactivé le compte de l'enseignant {cible}"),
                'refuse': ("modification", f"a refusé la demande de l'enseignant {cible}"),
                'desactive': ("modification", f"a désactivé le compte de l'enseignant {cible}"),
                'en_attente': ("modification", f"a remis en attente le compte de l'enseignant {cible}"),
            }
            action, texte = phrases.get(nouveau, ("modification", f"a changé le statut de {cible} ({nouveau})"))
            journal.enregistrer(request, 'enseignant', action, f"{qui} {texte}.", cible_id=instance.pk)
        if instance.email != ancien_email:
            journal.enregistrer(
                request, 'enseignant', 'modification',
                f"{qui} a modifié l'email de l'enseignant {cible} : "
                f"{ancien_email or '(vide)'} → {instance.email or '(vide)'}.", cible_id=instance.pk)


class ProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
