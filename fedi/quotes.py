"""FEP-044f quote post authorization.

Advertising ``interactionPolicy.canQuote`` is only advisory. Before a
remote server will show a quote of one of our posts, it sends a
``QuoteRequest`` to our inbox and waits for an ``Accept`` carrying a
dereferenceable ``QuoteAuthorization`` stamp. Until that stamp exists and
resolves, the quote stays stuck pending on the remote side.
"""

import logging

from .models import FediActivity, FediQuoteAuthorization
from .utils import post_activity
from .vocab import QUOTE_ACCEPT_CONTEXT, quote_is_automatically_approved

logger = logging.getLogger(__name__)


def _as_id(value):
    """QuoteRequest fields may be a bare URI or an embedded object."""
    if isinstance(value, dict):
        return value.get("id")
    if isinstance(value, str):
        return value
    return None


def handle_quote_request(actor, activity, remote_actor) -> bool:
    """Approve a QuoteRequest and deliver the Accept. True if approved."""
    target_id = _as_id(activity.get("object"))
    instrument_id = _as_id(activity.get("instrument"))
    request_id = activity.get("id")
    requesting_actor = activity.get("actor")

    if not target_id or not instrument_id or not request_id:
        logger.warning("QuoteRequest missing object/instrument/id: %s", request_id)
        return False

    # The Note being quoted has to be one of ours. Notes are published with
    # the same id as their wrapping Create, so the ap_id lookup matches.
    try:
        quoted = FediActivity.objects.get(actor=actor, ap_id=target_id)
    except FediActivity.DoesNotExist:
        logger.warning("QuoteRequest for unknown object %s", target_id)
        return False

    note = quoted.payload.get("object", quoted.payload)
    if not quote_is_automatically_approved(note):
        logger.info("QuoteRequest for %s not automatically approved", target_id)
        return False

    authorization, _ = FediQuoteAuthorization.objects.get_or_create(
        interaction_target=target_id,
        interacting_object=instrument_id,
        defaults={"actor": actor, "remote_actor_id": requesting_actor},
    )

    accept = {
        "@context": QUOTE_ACCEPT_CONTEXT,
        "type": "Accept",
        "id": f"{authorization.ap_id}#accept",
        "actor": actor.actor_id,
        "to": requesting_actor,
        "object": {
            "type": "QuoteRequest",
            "id": request_id,
            "actor": requesting_actor,
            "instrument": instrument_id,
            "object": target_id,
        },
        "result": authorization.ap_id,
    }

    inbox_url = remote_actor.get("inbox")
    if not inbox_url:
        logger.error("No inbox for %s, cannot send quote Accept", requesting_actor)
        return False

    try:
        post_activity(actor, inbox_url, accept)
        logger.info("Approved quote of %s by %s", target_id, instrument_id)
        return True
    except Exception as exc:
        logger.error("Failed to send quote Accept to %s: %s", inbox_url, exc)
        return False
