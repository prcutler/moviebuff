from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings

class Actor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    inbox = models.URLField(blank=True, null=True)
    outbox = models.URLField(blank=True, null=True)
    followers = models.URLField(blank=True, null=True)
    following = models.URLField(blank=True, null=True)

    def get_absolute_url(self):
        return f"{settings.DOMAIN_NAME}/activitypub/users/{self.user.username}/"

    def save(self, *args, **kwargs):
        if not self.inbox:
            self.inbox = f"{settings.DOMAIN_NAME}/activitypub/users/{self.user.username}/inbox/"
        if not self.outbox:
            self.outbox = f"{settings.DOMAIN_NAME}/activitypub/users/{self.user.username}/outbox/"
        if not self.followers:
            self.followers = f"{settings.DOMAIN_NAME}/activitypub/users/{self.user.username}/followers/"
        if not self.following:
            self.following = f"{settings.DOMAIN_NAME}/activitypub/users/{self.user.username}/following/"
        super().save(*args, **kwargs)

class Follow(models.Model):
    user_from = models.ForeignKey(User, related_name='following', on_delete=models.CASCADE)
    user_to = models.ForeignKey(User, related_name='followers', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)