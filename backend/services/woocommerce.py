import time

import requests
from core.config import STORE_URL, WC_KEY, WC_SECRET

# In-memory cache so we don't hit WooCommerce on every chat message.
# Refreshed at most once per TTL seconds (keeps replies fast).
_CACHE_TTL = int(__import__("os").getenv("CATALOG_CACHE_TTL", "300"))
_cache = {"products": None, "expires": 0}


def get_all_products(force=False):

    now = time.time()

    if not force and _cache["products"] is not None and now < _cache["expires"]:
        return _cache["products"]

    url = f"{STORE_URL}/wp-json/wc/v3/products"

    response = requests.get(
        url,
        auth=(WC_KEY, WC_SECRET),
        params={
            "per_page": 100
        },
        timeout=20
    )

    response.raise_for_status()

    products = response.json()
    _cache["products"] = products
    _cache["expires"] = now + _CACHE_TTL
    return products


def refresh_catalog_cache():
    """Force-refresh the cached catalogue (used by the startup sync hook)."""
    try:
        return get_all_products(force=True)
    except Exception:
        return _cache["products"]