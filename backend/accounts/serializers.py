from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import UserProfile


def _email_deja_utilise(email, exclure_pk=None):
    qs = User.objects.filter(email__iexact=email)
    if exclure_pk is not None:
        qs = qs.exclude(pk=exclure_pk)
    return qs.exists()


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['role', 'statut', 'telephone']


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    nom = serializers.CharField(source='last_name', required=False)
    prenom = serializers.CharField(source='first_name', required=False)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'nom', 'prenom', 'profile']


class InscriptionEnseignantSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    nom = serializers.CharField(write_only=True, max_length=150)
    prenom = serializers.CharField(write_only=True, max_length=150)
    telephone = serializers.CharField(
        write_only=True, required=False, allow_blank=True, max_length=30
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'nom', 'prenom', 'telephone']

    def validate_email(self, value):
        if _email_deja_utilise(value):
            raise serializers.ValidationError('Cette adresse email est déjà utilisée.')
        return value

    def validate(self, attrs):
        # Validateurs de mot de passe de Django (longueur, mots de passe
        # courants, tout-numérique, ressemblance avec le nom d'utilisateur...)
        utilisateur_temp = User(
            username=attrs.get('username', ''),
            email=attrs.get('email', ''),
            first_name=attrs.get('prenom', ''),
            last_name=attrs.get('nom', ''),
        )
        try:
            validate_password(attrs['password'], user=utilisateur_temp)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({'password': list(exc.messages)})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        telephone = validated_data.pop('telephone', '')
        nom = validated_data.pop('nom')
        prenom = validated_data.pop('prenom')
        password = validated_data.pop('password')

        user = User.objects.create_user(
            password=password,
            last_name=nom,
            first_name=prenom,
            **validated_data,
        )
        UserProfile.objects.create(
            user=user,
            role='enseignant',
            statut='en_attente',
            telephone=telephone or None,
        )
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    statut = serializers.ChoiceField(choices=UserProfile.STATUT_CHOICES, required=False)

    class Meta:
        model = User
        fields = ['email', 'statut']

    def validate_email(self, value):
        if value and _email_deja_utilise(value, exclure_pk=self.instance.pk):
            raise serializers.ValidationError('Cette adresse email est déjà utilisée.')
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        statut = validated_data.pop('statut', None)
        instance.email = validated_data.get('email', instance.email)
        instance.save()
        if statut is not None:
            instance.profile.statut = statut
            instance.profile.save()
        return instance
