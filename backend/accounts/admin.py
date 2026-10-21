from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'statut', 'telephone')
    list_filter = ('role', 'statut')
    search_fields = ('user__username', 'user__last_name', 'user__first_name')