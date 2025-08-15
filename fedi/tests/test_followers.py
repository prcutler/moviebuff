from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from fedi.models import FediFollower


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class FollowersTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self.actor = self.user.fediactor
        FediFollower.objects.create(
            actor=self.actor,
            remote_actor_id="https://remote.example/users/bob",
            inbox="https://remote.example/users/bob/inbox",
            state=FediFollower.ACCEPTED,
        )
        FediFollower.objects.create(
            actor=self.actor,
            remote_actor_id="https://remote.example/users/carol",
            inbox="https://remote.example/users/carol/inbox",
            state=FediFollower.ACCEPTED,
        )

    def test_followers_collection(self):
        response = self.client.get(
            "/users/alice/followers", HTTP_ACCEPT="application/activity+json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "Collection")
        self.assertEqual(data["totalItems"], 2)
        self.assertEqual(
            data["first"], "https://example.com/users/alice/followers?page=1"
        )
        self.assertEqual(
            data["last"], "https://example.com/users/alice/followers?page=1"
        )

    def test_followers_page(self):
        response = self.client.get(
            "/users/alice/followers?page=1", HTTP_ACCEPT="application/activity+json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "CollectionPage")
        self.assertCountEqual(
            data["items"],
            [
                "https://remote.example/users/bob",
                "https://remote.example/users/carol",
            ],
        )

