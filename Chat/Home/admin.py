from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "full_name",
        "mobile",
        "profession",
        "date_of_birth",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "mobile",
        "recovery_mobile",
        "profession",
    )

    list_filter = (
        "profession",
        "created_at",
        "updated_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )