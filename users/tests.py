from django.test import Client, TestCase
from django.contrib.auth.models import User


class ActorEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pass")

    def test_actor_returns_person_object(self):
        client = Client(HTTP_ACCEPT="application/activity+json")
        response = client.get(f"/users/{self.user.username}")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        actor_url = f"http://testserver/users/{self.user.username}"
        self.assertEqual(data["id"], actor_url)
        self.assertEqual(data["type"], "Person")
        self.assertEqual(data["preferredUsername"], self.user.username)
        self.assertEqual(data["inbox"], f"{actor_url}/inbox")
        self.assertEqual(data["outbox"], f"{actor_url}/outbox")
        self.assertEqual(data["followers"], f"{actor_url}/followers")

        public_key = data.get("publicKey")
        self.assertIsNotNone(public_key)
        self.assertEqual(public_key["id"], f"{actor_url}#main-key")
        self.assertEqual(public_key["owner"], actor_url)
        self.assertTrue(public_key["publicKeyPem"].startswith("-----BEGIN PUBLIC KEY-----"))

