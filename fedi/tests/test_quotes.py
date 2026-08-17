import json
import uuid
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from fedi.models import FediActivity, FediQuoteAuthorization
from fedi.utils import build_signed_headers
from fedi.views import inbox, quote_authorization
from fedi.vocab import PUBLIC, build_interaction_policy


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class QuoteRequestTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self.actor = self.user.fediactor
        self.actor_id = self.actor.actor_id

        self.remote_actor = "https://remote.example/users/bob"
        self.remote_inbox = "https://remote.example/users/bob/inbox"
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.remote_private_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        self.actor_json = {
            "id": self.remote_actor,
            "inbox": self.remote_inbox,
            "publicKey": {
                "id": f"{self.remote_actor}#main-key",
                "owner": self.remote_actor,
                "publicKeyPem": key.public_key()
                .public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                .decode(),
            },
        }

        self.note_id = f"https://example.com/activities/{uuid.uuid4()}"
        self.quote_post = "https://remote.example/users/bob/statuses/99"
        self.activity = FediActivity.objects.create(
            actor=self.actor,
            ap_id=self.note_id,
            type="Create",
            payload={
                "id": self.note_id,
                "type": "Create",
                "object": {
                    "id": self.note_id,
                    "type": "Note",
                    "content": "rated The Film 5/5",
                    "interactionPolicy": build_interaction_policy(self.actor),
                },
            },
        )

    def _post_to_inbox(self, activity):
        body = json.dumps(activity).encode()

        class Dummy:
            actor_id = self.remote_actor
            private_key_pem = self.remote_private_pem

        headers = build_signed_headers(
            Dummy(), "http://testserver/users/alice/inbox", body
        )
        request = RequestFactory().post(
            "/users/alice/inbox", body, content_type="application/activity+json"
        )
        request.META.update(
            {
                "HTTP_HOST": "testserver",
                "HTTP_DATE": headers["Date"],
                "HTTP_DIGEST": headers["Digest"],
                "HTTP_SIGNATURE": headers["Signature"],
            }
        )
        return inbox(request, "alice")

    def _quote_request(self):
        return {
            "type": "QuoteRequest",
            "id": "https://remote.example/users/bob/quote_requests/1",
            "actor": self.remote_actor,
            "object": self.note_id,
            "instrument": {
                "id": self.quote_post,
                "attributedTo": self.remote_actor,
                "quote": self.note_id,
            },
        }

    @patch("fedi.utils.requests.post")
    @patch("fedi.utils.requests.get")
    def test_quote_request_is_approved(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = self.actor_json
        mock_get.return_value.raise_for_status.return_value = None

        response = self._post_to_inbox(self._quote_request())
        self.assertEqual(response.status_code, 202)

        authorization = FediQuoteAuthorization.objects.get()
        self.assertEqual(authorization.interaction_target, self.note_id)
        self.assertEqual(authorization.interacting_object, self.quote_post)

        mock_post.assert_called_once()
        sent = json.loads(mock_post.call_args.kwargs["data"])
        self.assertEqual(sent["type"], "Accept")
        self.assertEqual(sent["actor"], self.actor_id)
        self.assertEqual(sent["object"]["type"], "QuoteRequest")
        # The stamp URL the remote server will dereference.
        self.assertEqual(sent["result"], authorization.ap_id)

    @patch("fedi.utils.requests.post")
    @patch("fedi.utils.requests.get")
    def test_quote_request_for_unknown_object_is_ignored(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = self.actor_json
        mock_get.return_value.raise_for_status.return_value = None

        request = self._quote_request()
        request["object"] = "https://example.com/activities/does-not-exist"
        response = self._post_to_inbox(request)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(FediQuoteAuthorization.objects.count(), 0)
        mock_post.assert_not_called()

    @patch("fedi.utils.requests.post")
    @patch("fedi.utils.requests.get")
    def test_quote_request_denied_when_policy_disallows(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = self.actor_json
        mock_get.return_value.raise_for_status.return_value = None

        payload = self.activity.payload
        payload["object"]["interactionPolicy"] = {
            "canQuote": {"automaticApproval": []}
        }
        self.activity.payload = payload
        self.activity.save()

        response = self._post_to_inbox(self._quote_request())
        self.assertEqual(response.status_code, 202)
        self.assertEqual(FediQuoteAuthorization.objects.count(), 0)
        mock_post.assert_not_called()

    @patch("fedi.utils.requests.post")
    @patch("fedi.utils.requests.get")
    def test_repeated_quote_request_reuses_stamp(self, mock_get, mock_post):
        mock_get.return_value.json.return_value = self.actor_json
        mock_get.return_value.raise_for_status.return_value = None

        self._post_to_inbox(self._quote_request())
        first = json.loads(mock_post.call_args.kwargs["data"])["result"]
        self._post_to_inbox(self._quote_request())
        second = json.loads(mock_post.call_args.kwargs["data"])["result"]

        self.assertEqual(first, second)
        self.assertEqual(FediQuoteAuthorization.objects.count(), 1)


@override_settings(
    ACTIVITYPUB_ENABLED=True,
    ACTIVITYPUB_DOMAIN="https://example.com",
    ROOT_URLCONF="moviebuff.urls",
)
class QuoteAuthorizationViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="alice", password="pwd")
        profile = self.user.userprofile
        profile.fedi_enabled = True
        profile.save()
        self.actor = self.user.fediactor
        self.authorization = FediQuoteAuthorization.objects.create(
            actor=self.actor,
            interaction_target="https://example.com/activities/abc",
            interacting_object="https://remote.example/users/bob/statuses/99",
            remote_actor_id="https://remote.example/users/bob",
        )

    def test_stamp_is_served(self):
        request = RequestFactory().get("/quote-authorizations/x")
        response = quote_authorization(request, self.authorization.uuid)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/activity+json")
        data = json.loads(response.content)
        self.assertEqual(data["type"], "QuoteAuthorization")
        self.assertEqual(data["id"], self.authorization.ap_id)
        self.assertEqual(data["attributedTo"], self.actor.actor_id)
        self.assertEqual(
            data["interactionTarget"], "https://example.com/activities/abc"
        )
        self.assertEqual(
            data["interactingObject"],
            "https://remote.example/users/bob/statuses/99",
        )
        # The FEP-044f terms must be declared or JSON-LD consumers drop them.
        self.assertIn("QuoteAuthorization", json.dumps(data["@context"]))

    def test_unknown_stamp_is_404(self):
        from django.http import Http404

        request = RequestFactory().get("/quote-authorizations/x")
        with self.assertRaises(Http404):
            quote_authorization(request, uuid.uuid4())


class InteractionPolicyTests(TestCase):
    def test_policy_uses_current_property_names(self):
        class Actor:
            followers_url = "https://example.com/users/alice/followers"

        policy = build_interaction_policy(Actor())
        # Mastodon and GoToSocial 0.21+ read automaticApproval; the older
        # automaticallyApprove spelling is silently ignored.
        self.assertIn("automaticApproval", policy["canQuote"])
        self.assertNotIn("automaticallyApprove", policy["canQuote"])
        self.assertIn(PUBLIC, policy["canQuote"]["automaticApproval"])
