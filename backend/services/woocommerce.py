import requests
from backend.core.config import STORE_URL, WC_KEY, WC_SECRET

def get_all_products():

    url = f"{STORE_URL}/wp-json/wc/v3/products"

    response = requests.get(
        url,
        auth=(WC_KEY, WC_SECRET),
        params={
            "per_page": 100
        }
    )

    response.raise_for_status()

    return response.json()