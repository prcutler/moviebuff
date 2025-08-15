from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class WebfingerTests(TestCase):
    def test_webfinger_success(self):
        User = get_user_model()
        user = User.objects.create_user(username="alice", password="pwd")
        profile = user.userprofile
        profile.fedi_enabled = True
        profile.save()

        response = self.client.get(
            "/.well-known/webfinger",
            {"resource": "acct:alice@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/jrd+json")
        data = response.json()
        self.assertEqual(data["subject"], "acct:alice@example.com")
        self.assertEqual(
            data["links"][0]["href"],
            "https://example.com/users/alice",
        )

    def test_webfinger_not_found_for_non_discoverable(self):
        User = get_user_model()
        user = User.objects.create_user(username="bob", password="pwd")
        profile = user.userprofile
        profile.fedi_enabled = True
        profile.fedi_discoverable = False
        profile.save()

        response = self.client.get(
            "/.well-known/webfinger",
            {"resource": "acct:bob@example.com"},
        )
        self.assertEqual(response.status_code, 404)
