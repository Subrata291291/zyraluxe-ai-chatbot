import requests
from core.config import OPENROUTER_API_KEY

MODEL = "meta-llama/llama-3.1-8b-instruct"

API_URL = "https://openrouter.ai/api/v1/chat/completions"


def ask_ai(user_question, products, query=None):
    """
    Generate an AI response using matching WooCommerce products.
    """

    query = query or {}

    # If no products found
    if not products:
        return (
            "Sorry, I couldn't find any matching products in our store. "
            "Could you try a different keyword?"
        )

    # Prepare product information
    product_text = ""

    for product in products:
        categories = ", ".join(
            c["name"] for c in product.get("categories", [])
        )

        product_text += f"""
Name: {product.get('name', '')}
Price: Rs.{product.get('price', '')}
Stock: {product.get('stock_status', '')}
Category: {categories}
Rating: {product.get('average_rating', '0')} out of 5
Review count: {product.get('rating_count', 0)}
Total sales: {product.get('total_sales', 0)}
----------------------------------------
"""

    sort_instruction = ""

    if query.get("sort") == "best_selling":
        sort_instruction = "The products are already sorted by best-selling order. Recommend them in this exact order."

    if query.get("sort") == "top_rated":
        sort_instruction = "The products are already sorted by rating. Recommend them in this exact order."

    prompt =  f"""
You are the AI shopping assistant for our jewellery store.

IMPORTANT RULES:

- Only recommend products listed below.
- Do NOT create, guess, or invent products.
- If a product is not listed, never mention it.
- Mention only the product name, price, stock, and rating exactly as provided.
- Keep the response short and readable.
- Do not use markdown bold formatting.
- If there are no matching products, say:
  "Sorry, I couldn't find a matching product."
- {sort_instruction}

Products:

{product_text}

Customer Question:

{user_question}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a professional jewellery shopping assistant."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.4,
        "max_tokens": 350
    }

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        data = response.json()

        return data["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        return f"API Error: {e}"

    except KeyError:
        return "Unexpected response received from OpenRouter."
