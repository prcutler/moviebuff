from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class ProfileToggleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="alice", password="pwd", email="a@example.com"
        )

    def test_update_fediverse_settings(self):
        self.client.login(username="alice", password="pwd")
        url = reverse("user_profile", args=["alice"])
        response = self.client.post(
            url, {"fedi_enabled": "on", "fedi_discoverable": "on"}
        )
        self.assertEqual(response.status_code, 302)
        profile = self.user.userprofile
        profile.refresh_from_db()
        self.assertTrue(profile.fedi_enabled)
        self.assertTrue(profile.fedi_discoverable)
