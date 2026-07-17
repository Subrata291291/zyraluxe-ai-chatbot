import requests
from core.config import OPENROUTER_API_KEY
from services.rag import get_knowledge_context

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


def ask_conversation(user_message, intent="general", filters=None):
    """
    Generate a free-form, natural reply for non-product turns
    (greetings, thanks, small talk, policy/FAQ questions, and
    filter-collection prompts) using the LLM so the wording is dynamic
    and on-brand instead of hardcoded. Falls back to a safe static
    string if the API fails.
    """

    filters = filters or {}

    # Pull relevant knowledge-base snippets (Level 1 RAG)
    kb_context = get_knowledge_context(user_message)

    # Build a short summary of what we already know about the shopper
    known = []
    if filters.get("category"):
        known.append(f"category: {filters['category']}")
    if filters.get("material"):
        known.append(f"material: {filters['material']}")
    if filters.get("keyword"):
        known.append(f"keyword: {filters['keyword']}")
    if filters.get("budget"):
        known.append(f"budget: under Rs.{filters['budget']}")
    if filters.get("min_rating"):
        known.append(f"min rating: {filters['min_rating']} star and above")

    known_text = ", ".join(known) if known else "nothing yet"

    kb_block = kb_context if kb_context else "(no relevant knowledge found)"

    prompt = f"""
You are the friendly AI shopping assistant for Zyraluxe, a jewellery store.
Your job is to keep the conversation natural, warm, and on-brand.

Shopper message: "{user_message}"
Detected intent: {intent}
What we already know about the shopper: {known_text}

 Rules:
- Reply like a real human sales assistant, 1-2 short sentences.
- If intent is "greeting", welcome them and ask what jewellery they want (necklace, earrings, ring, jhumka, bangle, pendant, etc).
- If intent is "thanks", thank them warmly and invite them back.
- If the shopper just said they have no preference (e.g. "any", "doesn't matter"), acknowledge it briefly and move on.
- If we still need a budget, ask for a price range naturally (e.g. under Rs.500, under Rs.1000) and offer "any" as an option.
- If we still need a rating, ask for a minimum rating naturally (e.g. 4 star and above) and offer "any" as an option.
- Do NOT recommend specific products here. Do NOT use markdown. Keep it short.

 KNOWLEDGE BASE (use this to answer store policy, shipping, returns, sizing,
 care, materials, and FAQ questions accurately):
{kb_block}
- If the question is about store policy/shipping/returns/materials/care/FAQ and the KNOWLEDGE BASE above has relevant info, answer ONLY from it, concisely and accurately. Quote the real numbers (e.g. return window, free-shipping threshold, prices) exactly as written.
- When asked whether items are real gold/diamond/silver or what materials you use, answer directly from the KNOWLEDGE BASE (Zyraluxe sells fashion/costume jewellery — alloy, oxidised/german silver, rhodium-plated, pearl, kundan, beads, stones — NOT solid gold or certified diamonds). Do NOT invent prices for this.
- Do NOT invent details, prices, policies, or products that are not in the KNOWLEDGE BASE or the product list. If the answer is not in the provided context, say you are not sure and suggest emailing zyraluxeofficial@gmail.com.
- Keep replies short (1-3 sentences) and friendly. Do NOT use markdown.
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
                "content": "You are a professional jewellery shopping assistant for Zyraluxe.",
            },
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.7,
        "max_tokens": 120,
    }

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        return data["choices"][0]["message"]["content"].strip()

    except Exception:
        # Safe static fallbacks so the bot never breaks if the LLM is down.
        # If we have knowledge-base content, answer straight from it.
        if kb_context:
            return kb_context

        if intent == "greeting":
            return "Hello! Welcome to Zyraluxe. What kind of jewellery are you looking for today?"
        if intent == "thanks":
            return "You're welcome. I'm here whenever you want help choosing jewellery."
        if filters.get("budget") is None:
            return "Sure. What price range should I keep in mind? For example: under Rs.500, under Rs.1000, or say any."
        if filters.get("min_rating") is None:
            return "Got it. Do you want a minimum rating? For example: 4 star and above, 5 star, or say any."
        return "I can help you find jewellery step by step. Tell me the product or style you want, like necklace, earrings, jhumka, ring, or pearl set."
