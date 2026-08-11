from local.api_app.models.apikey_model import API_KEY_PREFIX, ApiKeyModel, hash_api_key


def is_api_key(token: str) -> bool:
    if not token:
        return False
    return token.startswith(API_KEY_PREFIX)


def resolve_api_key(token: str):
    """Returns a request.user-shaped identity dict for a valid, non-revoked key, else None."""
    if not token:
        return None
    row = ApiKeyModel.find_by_hash(hash_api_key(token))
    if not row:
        return None
    try:
        ApiKeyModel.touch_last_used(row.id)
    except Exception:
        # Best-effort bookkeeping only; a failed last-used write must not turn an
        # already-verified key into an auth failure.
        pass
    return {"id": f"apikey:{row.id}", "role": "service", "project_id": row.project_id}
