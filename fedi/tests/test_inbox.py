import json
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from fedi.models import FediFollower
from fedi.utils import build_signed_headers
from fedi.views import inbox


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class InboxTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self.actor_id = self.user.fediactor.actor_id

        # remote actor setup
        self.remote_actor = "https://remote.example/users/bob"
        self.remote_inbox = "https://remote.example/users/bob/inbox"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.remote_private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        self.remote_public_pem = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        self.actor_json = {
            "id": self.remote_actor,
            "inbox": self.remote_inbox,
            "publicKey": {
                "id": f"{self.remote_actor}#main-key",
                "owner": self.remote_actor,
                "publicKeyPem": self.remote_public_pem,
            },
        }

    def _signed_headers(self, body: bytes):
        class Dummy:
            actor_id = self.remote_actor
            private_key_pem = self.remote_private_pem

        headers = build_signed_headers(
            Dummy(), "http://testserver/users/alice/inbox", body
        )
        return {
            "HTTP_HOST": "testserver",
            "HTTP_DATE": headers["Date"],
            "HTTP_DIGEST": headers["Digest"],
            "HTTP_SIGNATURE": headers["Signature"],
        }

    @patch("fedi.utils.requests.post")
    @patch("fedi.utils.requests.get")
    def test_follow_accept(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = self.actor_json
        mock_get.return_value.raise_for_status.return_value = None
        follow = {
            "type": "Follow",
            "actor": self.remote_actor,
            "object": self.actor_id,
        }
        body = json.dumps(follow).encode()
        headers = self._signed_headers(body)
        rf = RequestFactory()
        request = rf.post(
            "/users/alice/inbox", body, content_type="application/activity+json"
        )
        request.META.update(headers)
        response = inbox(request, "alice")
        self.assertEqual(response.status_code, 202)
        follower = FediFollower.objects.get()
        self.assertEqual(follower.remote_actor_id, self.remote_actor)
        self.assertEqual(follower.state, FediFollower.ACCEPTED)
        mock_post.assert_called_once()
        sent = json.loads(mock_post.call_args.kwargs["data"])
        self.assertEqual(sent["type"], "Accept")

    @patch("fedi.utils.requests.post")
    @patch("fedi.utils.requests.get")
    def test_follow_reject_when_disabled(self, mock_get, mock_post):
        profile = self.user.userprofile
        profile.fedi_enabled = False
        profile.save()
        mock_get.return_value.json.return_value = self.actor_json
        mock_get.return_value.raise_for_status.return_value = None
        follow = {
            "type": "Follow",
            "actor": self.remote_actor,
            "object": self.actor_id,
        }
        body = json.dumps(follow).encode()
        headers = self._signed_headers(body)
        rf = RequestFactory()
        request = rf.post(
            "/users/alice/inbox", body, content_type="application/activity+json"
        )
        request.META.update(headers)
        response = inbox(request, "alice")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(FediFollower.objects.count(), 0)
        mock_post.assert_called_once()
        sent = json.loads(mock_post.call_args.kwargs["data"])
        self.assertEqual(sent["type"], "Reject")

    @patch("fedi.utils.requests.post")
    @patch("fedi.utils.requests.get")
    def test_undo_follow(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = self.actor_json
        mock_get.return_value.raise_for_status.return_value = None
        follow = {
            "type": "Follow",
            "actor": self.remote_actor,
            "object": self.actor_id,
        }
        body = json.dumps(follow).encode()
        headers = self._signed_headers(body)
        rf = RequestFactory()
        request = rf.post(
            "/users/alice/inbox", body, content_type="application/activity+json"
        )
        request.META.update(headers)
        inbox(request, "alice")
        self.assertEqual(FediFollower.objects.count(), 1)
        mock_post.reset_mock()
        undo = {
            "type": "Undo",
            "actor": self.remote_actor,
            "object": {
                "type": "Follow",
                "actor": self.remote_actor,
                "object": self.actor_id,
            },
        }
        body2 = json.dumps(undo).encode()
        headers2 = self._signed_headers(body2)
        request2 = rf.post(
            "/users/alice/inbox", body2, content_type="application/activity+json"
        )
        request2.META.update(headers2)
        response = inbox(request2, "alice")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(FediFollower.objects.count(), 0)
        mock_post.assert_not_called()

