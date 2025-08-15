from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class ActorTests(TestCase):
    def test_actor_success(self):
        User = get_user_model()
        user = User.objects.create_user(username="alice", password="pwd")
        profile = user.userprofile
        profile.fedi_enabled = True
        profile.save()

        response = self.client.get(
            "/users/alice", HTTP_ACCEPT="application/activity+json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/activity+json")
        data = response.json()
        self.assertEqual(data["id"], "https://example.com/users/alice")
        self.assertEqual(data["type"], "Person")
        self.assertEqual(data["preferredUsername"], "alice")
        self.assertEqual(data["inbox"], "https://example.com/users/alice/inbox")
        self.assertEqual(data["outbox"], "https://example.com/users/alice/outbox")
        self.assertEqual(data["followers"], "https://example.com/users/alice/followers")
        self.assertEqual(
            data["publicKey"]["id"], "https://example.com/users/alice#main-key"
        )
        self.assertEqual(data["publicKey"]["owner"], "https://example.com/users/alice")
        self.assertTrue(
            data["publicKey"]["publicKeyPem"].startswith("-----BEGIN PUBLIC KEY-----")
        )

    def test_actor_not_found_for_non_fedi_enabled(self):
        User = get_user_model()
        User.objects.create_user(username="bob", password="pwd")
        response = self.client.get(
            "/users/bob", HTTP_ACCEPT="application/activity+json"
        )
        self.assertEqual(response.status_code, 404)
