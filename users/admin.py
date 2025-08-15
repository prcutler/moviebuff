from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "fedi_enabled", "fedi_discoverable")
    list_filter = ("fedi_enabled", "fedi_discoverable")

