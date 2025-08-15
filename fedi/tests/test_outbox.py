from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from fedi.models import FediActivity


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class OutboxTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self.actor = self.user.fediactor
        for i in range(3):
            FediActivity.objects.create(
                actor=self.actor,
                ap_id=f"https://example.com/activities/{i}",
                type="Note",
                payload={
                    "id": f"https://example.com/activities/{i}",
                    "type": "Note",
                },
            )

    def test_outbox_collection(self):
        response = self.client.get(
            "/users/alice/outbox", HTTP_ACCEPT="application/activity+json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "OrderedCollection")
        self.assertEqual(data["totalItems"], 3)
        self.assertEqual(
            data["first"], "https://example.com/users/alice/outbox?page=1"
        )
        self.assertEqual(
            data["last"], "https://example.com/users/alice/outbox?page=1"
        )

    def test_outbox_page(self):
        response = self.client.get(
            "/users/alice/outbox?page=1", HTTP_ACCEPT="application/activity+json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "OrderedCollectionPage")
        self.assertEqual(len(data["orderedItems"]), 3)
        self.assertEqual(
            data["orderedItems"][0]["id"], "https://example.com/activities/2"
        )
        self.assertEqual(
            data["orderedItems"][1]["id"], "https://example.com/activities/1"
        )
        self.assertEqual(
            data["orderedItems"][2]["id"], "https://example.com/activities/0"
        )

