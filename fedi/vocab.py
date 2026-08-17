"""Shared JSON-LD vocabulary for outgoing ActivityPub documents.

Interaction policies and the FEP-044f quote terms live in extension
namespaces. A document that uses them without declaring them in its
@context is still valid JSON, but strict JSON-LD processors drop the
undeclared terms — so the policy silently disappears on the receiving
side. Every builder here emits the terms it actually uses.
"""

PUBLIC = "https://www.w3.org/ns/activitystreams#Public"

AS_NS = "https://www.w3.org/ns/activitystreams"
GTS_NS = "https://gotosocial.org/ns#"
FEP_044F = "https://w3id.org/fep/044f#"

_INTERACTION_POLICY_TERMS = {
    "gts": GTS_NS,
    "interactionPolicy": {"@id": "gts:interactionPolicy", "@type": "@id"},
    "canQuote": {"@id": "gts:canQuote", "@type": "@id"},
    "canReblog": {"@id": "gts:canReblog", "@type": "@id"},
    "automaticApproval": {"@id": "gts:automaticApproval", "@type": "@id"},
    "manualApproval": {"@id": "gts:manualApproval", "@type": "@id"},
}

# Context for a Note (and the Create that wraps it) carrying an
# interactionPolicy.
NOTE_CONTEXT = [AS_NS, dict(_INTERACTION_POLICY_TERMS)]

# Context for the Accept we send in response to a QuoteRequest.
QUOTE_ACCEPT_CONTEXT = [
    AS_NS,
    {"QuoteRequest": f"{FEP_044F}QuoteRequest"},
]

# Context for the QuoteAuthorization stamp that third-party servers fetch
# to verify a quote was approved.
QUOTE_AUTHORIZATION_CONTEXT = [
    AS_NS,
    {
        "gts": GTS_NS,
        "QuoteAuthorization": {
            "@id": f"{FEP_044F}QuoteAuthorization",
            "@type": "@id",
        },
        "interactingObject": {"@id": "gts:interactingObject", "@type": "@id"},
        "interactionTarget": {"@id": "gts:interactionTarget", "@type": "@id"},
    },
]


def build_interaction_policy(actor):
    """Allow the public to reblog and quote posts by ``actor``.

    Mastodon collapses the audience lists down to public/followers/
    following/nobody and defaults to *nobody*, so the Public URI has to be
    listed explicitly for quoting to be allowed at all.
    """
    audience = [PUBLIC, actor.followers_url]
    return {
        "canReblog": {"automaticApproval": audience},
        "canQuote": {"automaticApproval": audience},
    }


def quote_is_automatically_approved(note: dict) -> bool:
    """Whether ``note``'s interactionPolicy lets anyone quote it."""
    policy = note.get("interactionPolicy") or {}
    approval = (policy.get("canQuote") or {}).get("automaticApproval")
    if approval is None:
        return False
    if isinstance(approval, str):
        approval = [approval]
    return PUBLIC in approval
