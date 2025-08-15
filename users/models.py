from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    fedi_enabled = models.BooleanField(default=False)
    fedi_discoverable = models.BooleanField(default=True)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=UserProfile)
def manage_fedi_actor(sender, instance, **kwargs):
    if not settings.ACTIVITYPUB_ENABLED:
        return

    from fedi.models import FediActor

    actor = getattr(instance.user, "fediactor", None)
    if instance.fedi_enabled:
        if not actor:
            domain = settings.ACTIVITYPUB_DOMAIN.rstrip("/")
            username = instance.user.username
            base = f"{domain}/users/{username}"
            actor = FediActor.objects.create(
                user=instance.user,
                actor_id=base,
                inbox_url=f"{base}/inbox",
                outbox_url=f"{base}/outbox",
                followers_url=f"{base}/followers",
                discoverable=instance.fedi_discoverable,
            )
    if actor and actor.discoverable != instance.fedi_discoverable:
        actor.discoverable = instance.fedi_discoverable
        actor.save()

