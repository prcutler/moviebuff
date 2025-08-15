from django.contrib import admin

from .models import FediActor, FediFollower, FediActivity, FediDelivery


@admin.register(FediActor)
class FediActorAdmin(admin.ModelAdmin):
    list_display = ("user", "actor_id", "discoverable", "created_at")


@admin.register(FediFollower)
class FediFollowerAdmin(admin.ModelAdmin):
    list_display = ("actor", "remote_actor_id", "state", "created_at")
    list_filter = ("state",)


@admin.register(FediActivity)
class FediActivityAdmin(admin.ModelAdmin):
    list_display = ("actor", "ap_id", "type", "created_at")


@admin.register(FediDelivery)
class FediDeliveryAdmin(admin.ModelAdmin):
    list_display = ("activity", "follower", "status", "last_http_status", "retry_count")
    list_filter = ("status",)

