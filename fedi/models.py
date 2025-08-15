from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


class FediActor(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    actor_id = models.URLField(unique=True)
    inbox_url = models.URLField()
    outbox_url = models.URLField()
    followers_url = models.URLField()
    public_key_pem = models.TextField(blank=True)
    private_key_pem = models.TextField(blank=True)
    discoverable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.public_key_pem or not self.private_key_pem:
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            self.private_key_pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode()
            self.public_key_pem = key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()
        super().save(*args, **kwargs)


class FediFollower(models.Model):
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    STATE_CHOICES = [
        (PENDING, "Pending"),
        (ACCEPTED, "Accepted"),
        (BLOCKED, "Blocked"),
    ]

    actor = models.ForeignKey(FediActor, on_delete=models.CASCADE, related_name="followers")
    remote_actor_id = models.URLField()
    inbox = models.URLField()
    shared_inbox = models.URLField(blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(blank=True)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FediActivity(models.Model):
    actor = models.ForeignKey(FediActor, on_delete=models.CASCADE, related_name="activities")
    ap_id = models.URLField(unique=True)
    type = models.CharField(max_length=50)
    payload = models.JSONField()
    visibility = models.CharField(max_length=20, default="public")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FediDelivery(models.Model):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    STATUS_CHOICES = [
        (QUEUED, "Queued"),
        (SENT, "Sent"),
        (FAILED, "Failed"),
    ]

    activity = models.ForeignKey(FediActivity, on_delete=models.CASCADE, related_name="deliveries")
    follower = models.ForeignKey(FediFollower, on_delete=models.CASCADE, related_name="deliveries")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=QUEUED)
    last_http_status = models.IntegerField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

