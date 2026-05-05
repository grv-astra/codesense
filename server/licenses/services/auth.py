import json
import os
from datetime import datetime, timezone
from functools import wraps

import requests
from django.conf import settings
from django.http import JsonResponse

DEFAULT_LICENSE_DIR = "./license_data"


def _license_dir():
    configured_dir = getattr(settings, "LOCAL_KEYS_DIR", None)
    if configured_dir and os.path.exists(configured_dir):
        return configured_dir
    return DEFAULT_LICENSE_DIR


def _config_path():
    return os.path.join(_license_dir(), "license_config.json")


def _token_path():
    return os.path.join(_license_dir(), "assertion_jwt.json")


def _private_key_path(config):
    return config.get("local_private_key_path") or os.path.join(_license_dir(), "local_private.pem")


def _central_url(config=None):
    url = (
        (config or {}).get("central_url")
        or getattr(settings, "CENTRAL_URL", None)
        or "http://localhost:8000"
    )
    return url.rstrip("/")


def load_config():
    with open(_config_path(), "r") as f:
        return json.load(f)


def load_assertion_jwt():
    token_path = _token_path()
    if not os.path.exists(token_path):
        return None
    with open(token_path, "r") as f:
        data = json.load(f)
        if data.get("exp") and datetime.now(timezone.utc).timestamp() < data["exp"]:
            return data["token"]
    return None


def save_assertion_jwt(token, exp):
    token_path = _token_path()
    os.makedirs(os.path.dirname(token_path), exist_ok=True)
    with open(token_path, "w") as f:
        json.dump({"token": token, "exp": exp}, f)


def refresh_assertion():
    """
    Perform challenge + assertion with Central to get a new assertion_jwt.
    """
    config = load_config()
    license_id = config["license_id"]
    local_id = config.get("local_id")
    provisioning_jwt = config.get("provisioning_jwt")
    central_url = _central_url(config)

    r = requests.post(
        f"{central_url}/api/local/challenge/",
        json={
            "license_id": license_id,
            "local_id": local_id,
            "provisioning_jwt": provisioning_jwt,
        },
        timeout=15,
    )
    r.raise_for_status()
    nonce = r.json()["nonce"]

    from licenses.services.crypto import load_private_key, sign_nonce

    private_key = load_private_key(_private_key_path(config))
    signed_nonce = sign_nonce(private_key, nonce)

    body = {
        "license_id": license_id,
        "local_id": local_id,
        "provisioning_jwt": provisioning_jwt,
        "nonce": nonce,
        "signed_nonce": signed_nonce,
    }

    r2 = requests.post(f"{central_url}/api/local/assertion/", json=body, timeout=15)
    r2.raise_for_status()
    data = r2.json()

    token = data["assertion_jwt"]
    exp = data.get("exp", int(datetime.now(timezone.utc).timestamp()) + 600)
    save_assertion_jwt(token, exp)
    return token


def update_usage(usage_type):
    """
    Call Central to increment usage AFTER a successful local action.
    usage_type: "scan" | "user"
    """
    config = load_config()
    license_id = config["license_id"]
    central_url = _central_url(config)

    r = requests.post(
        f"{central_url}/api/local/update-usage/",
        json={
            "license_id": license_id,
            "usage_type": usage_type,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def maybe_use_cached_assertion():
    token = load_assertion_jwt()
    if token:
        return token
    return refresh_assertion()


def require_assertion_jwt(usage_type=None, force_refresh=False):
    """
    Decorator for protecting local APIs that need a valid license assertion.
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            try:
                request = args[1] if len(args) > 1 else args[0]
                token = refresh_assertion() if force_refresh else maybe_use_cached_assertion()
                request.assertion_jwt = token

                response = view_func(*args, **kwargs)

                if usage_type and getattr(response, "status_code", 500) < 400:
                    update_usage(usage_type)

                return response

            except Exception as e:
                return JsonResponse({"error": str(e)}, status=401)

        return wrapper

    return decorator
