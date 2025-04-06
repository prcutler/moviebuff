from django.conf import settings
import requests
from .models import Actor

def publish_activity(actor, activity_type, object_content, to_list):
    activity = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": activity_type,
        "actor": actor.get_absolute_url(),
        "object": {
            "type": "Note",
            "content": object_content,
        },
        "to": to_list,
    }

    for follower_url in to_list:
        try:
            response = requests.post(
                follower_url,
                json=activity,
                headers={"Content-Type": "application/activity+json"}
            )
            if response.status_code != 200:
                print(f"Failed to deliver activity to {follower_url}: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request failed: {e}")
