import base64
import hashlib
import json
from email.utils import formatdate
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)


class HttpSignatureError(Exception):
    """Raised when an HTTP signature cannot be verified."""


def fetch_actor(actor_id: str) -> dict:
    """Fetch a remote actor and return its JSON data."""
    from django.conf import settings
    user_agent = getattr(settings, "ACTIVITYPUB_USER_AGENT", "moviebuff-activitypub")
    headers = {
        "Accept": "application/activity+json",
        "User-Agent": user_agent,
    }
    response = requests.get(actor_id, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def parse_signature_header(header: str) -> dict:
    parts = header.split(",")
    params = {}
    for part in parts:
        if "=" not in part:
            continue
        k, v = part.strip().split("=", 1)
        params[k] = v.strip("\"")
    return params


def verify_http_signature(request) -> dict:
    """Verify the HTTP signature of an incoming request.

    Returns the remote actor JSON on success.
    """
    sig_header = request.headers.get("Signature")
    if not sig_header:
        raise HttpSignatureError("Missing Signature header")
    params = parse_signature_header(sig_header)
    key_id = params.get("keyId")
    headers_list = params.get("headers", "").split()
    signature_b64 = params.get("signature")
    if not key_id or not headers_list or not signature_b64:
        raise HttpSignatureError("Invalid Signature header")

    # Build the signed string
    signed_parts = []
    for header in headers_list:
        if header == "(request-target)":
            value = f"{request.method.lower()} {request.get_full_path()}"
        else:
            value = request.headers.get(header)
            if value is None:
                raise HttpSignatureError(f"Missing header {header}")
        signed_parts.append(f"{header}: {value}")
    signed_string = "\n".join(signed_parts)

    # Fetch actor to get public key
    actor_id = key_id.split("#", 1)[0]
    actor_data = fetch_actor(actor_id)
    public_key_pem = actor_data.get("publicKey", {}).get("publicKeyPem")
    if not public_key_pem:
        raise HttpSignatureError("No public key")
    public_key = load_pem_public_key(public_key_pem.encode())

    # Verify signature
    signature = base64.b64decode(signature_b64)
    try:
        public_key.verify(
            signature,
            signed_string.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except Exception as exc:
        raise HttpSignatureError("Bad signature") from exc

    # Verify digest if provided
    digest_header = request.headers.get("Digest")
    if digest_header:
        body_digest = base64.b64encode(hashlib.sha256(request.body).digest()).decode()
        expected = f"SHA-256={body_digest}"
        if digest_header != expected:
            raise HttpSignatureError("Bad digest")

    return actor_data


def build_signed_headers(actor, url: str, body: bytes) -> dict:
    """Build headers with HTTP signatures for an outgoing request."""
    parsed = urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    signed_string = (
        f"(request-target): post {path}\n"
        f"host: {host}\n"
        f"date: {date}\n"
        f"digest: SHA-256={digest}"
    )
    private_key = load_pem_private_key(actor.private_key_pem.encode(), password=None)
    signature = base64.b64encode(
        private_key.sign(signed_string.encode(), padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    headers = {
        "Host": host,
        "Date": date,
        "Digest": f"SHA-256={digest}",
        "Signature": (
            f'keyId="{actor.actor_id}#main-key",algorithm="rsa-sha256",'
            f'headers="(request-target) host date digest",signature="{signature}"'
        ),
        "Content-Type": "application/activity+json",
    }
    return headers


def post_activity(actor, url: str, activity: dict) -> None:
    body = json.dumps(activity).encode()
    headers = build_signed_headers(actor, url, body)
    requests.post(url, data=body, headers=headers, timeout=10)

