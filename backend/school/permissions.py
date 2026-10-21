from rest_framework import permissions


def user_is_admin(user):
    return hasattr(user, 'profile') and user.profile.role == 'admin'


def user_is_enseignant_valide(user):
    return (
        hasattr(user, 'profile')
        and user.profile.role == 'enseignant'
        and user.profile.statut == 'valide'
    )


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and user_is_admin(request.user)


class IsEnseignantOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return user_is_admin(request.user) or user_is_enseignant_valide(request.user)
