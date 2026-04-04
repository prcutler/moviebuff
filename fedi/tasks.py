import logging

from .models import FediDelivery
from .utils import post_activity

logger = logging.getLogger(__name__)


def deliver_activity(activity_id, follower_id):
    """Deliver a single activity to a follower's inbox."""
    try:
        delivery = FediDelivery.objects.select_related(
            "activity__actor", "follower"
        ).get(activity_id=activity_id, follower_id=follower_id)
    except FediDelivery.DoesNotExist:
        logger.error("FediDelivery not found: activity=%s follower=%s", activity_id, follower_id)
        return

    if delivery.status == FediDelivery.SENT:
        return

    follower = delivery.follower
    inbox_url = follower.shared_inbox or follower.inbox
    actor = delivery.activity.actor

    try:
        post_activity(actor, inbox_url, delivery.activity.payload)
        delivery.status = FediDelivery.SENT
        delivery.last_error = ""
        delivery.save(update_fields=["status", "last_error", "updated_at"])
        logger.info("Delivered activity %s to %s", activity_id, inbox_url)
    except Exception as exc:
        delivery.status = FediDelivery.FAILED
        delivery.retry_count += 1
        delivery.last_error = str(exc)
        delivery.save(update_fields=["status", "retry_count", "last_error", "updated_at"])
        logger.error("Failed to deliver activity %s to %s: %s", activity_id, inbox_url, exc)
