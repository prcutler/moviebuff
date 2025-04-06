from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.http import JsonResponse
from .models import Follow, Actor
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json

@method_decorator(csrf_exempt, name='dispatch')
class InboxView(View):
    def post(self, request, username):
        try:
            activity = json.loads(request.body)
            # Traitez l'activité reçue ici
            print(f"Received activity: {activity}")
            return JsonResponse({"status": "success"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

def actor_detail(request, username):
    actor = get_object_or_404(Actor, user__username=username)
    return JsonResponse({
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": actor.get_absolute_url(),
        "type": "Person",
        "name": actor.user.username,
        "preferredUsername": actor.user.username,
        "inbox": actor.inbox,
        "outbox": actor.outbox,
        "followers": actor.followers,
        "following": actor.following,
    })

def follow_user(request, username):
    user_to_follow = get_object_or_404(User, username=username)
    Follow.objects.get_or_create(user_from=request.user, user_to=user_to_follow)
    return redirect('user_profile', username=username)

def unfollow_user(request, username):
    user_to_unfollow = get_object_or_404(User, username=username)
    Follow.objects.filter(user_from=request.user, user_to=user_to_unfollow).delete()
    return redirect('user_profile', username=username)

def followers(request, username):
    user = get_object_or_404(User, username=username)
    followers = Follow.objects.filter(user_to=user)
    return JsonResponse({
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"{settings.DOMAIN_NAME}/activitypub/users/{username}/followers/",
        "type": "OrderedCollection",
        "totalItems": followers.count(),
        "items": [follower.user_from.actor.get_absolute_url() for follower in followers]
    })

def following(request, username):
    user = get_object_or_404(User, username=username)
    following = Follow.objects.filter(user_from=user)
    return JsonResponse({
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"{settings.DOMAIN_NAME}/activitypub/users/{username}/following/",
        "type": "OrderedCollection",
        "totalItems": following.count(),
        "items": [follow.user_to.actor.get_absolute_url() for follow in following]
    })

def webfinger(request):
    resource = request.GET.get('resource')
    if not resource:
        return JsonResponse({"error": "Missing resource parameter"}, status=400)

    # Extrait le nom d'utilisateur et le domaine à partir du paramètre resource
    if resource.startswith("acct:"):
        username = resource[5:].split('@')[0]
    else:
        return JsonResponse({"error": "Invalid resource format"}, status=400)

    user = get_object_or_404(User, username=username)
    actor = get_object_or_404(Actor, user=user)

    webfinger_response = {
        "subject": f"acct:{username}@{request.get_host()}",
        "aliases": [
            actor.get_absolute_url(),
        ],
        "links": [
            {
                "rel": "self",
                "type": "application/activity+json",
                "href": actor.get_absolute_url()
            }
        ]
    }

    return JsonResponse(webfinger_response)