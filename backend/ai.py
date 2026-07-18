import time

import requests
from core.config import OPENROUTER_API_KEY, AI_MODEL
from services.rag import get_knowledge_context

MODEL = AI_MODEL

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Small retry budget for transient network errors / free-tier rate limits.
_MAX_RETRIES = 2
_RETRY_BACKOFF = 1.0


def _missing_key():
    return (
        "I'm not configured yet — the store's AI key is missing. "
        "Please contact the store owner to finish the setup."
    )


def _post(payload, timeout):
    """POST to OpenRouter with a couple of retries on transient failures."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    last_err = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.post(
                API_URL, headers=headers, json=payload, timeout=timeout
            )
            # Retry on 429 (rate limit) / 5xx with a short backoff.
            if response.status_code in (429, 500, 502, 503, 504) and attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            last_err = e
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF * (attempt + 1))
                continue
    raise last_err


def _format_history(history):
    """Render recent turns as readable text for the model prompt."""
    if not history:
        return ""
    lines = []
    for turn in history[-6:]:
        role = "Customer" if turn.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {turn.get('content', '')}")
    return "\n".join(lines)


def ask_ai(user_question, products, query=None, history=None):
    """
    Generate an AI response using matching WooCommerce products.
    """

    query = query or {}
    history = history or []

    # If no products found
    if not products:
        return (
            "Sorry, I couldn't find any matching products in our store. "
            "Could you try a different keyword or tell me the style you like?"
        )

    if not OPENROUTER_API_KEY:
        return _missing_key()

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
Product link: {product.get('permalink', '')}
----------------------------------------
"""

    sort_instruction = ""

    if query.get("sort") == "best_selling":
        sort_instruction = "The products are already sorted by best-selling order. Recommend them in this exact order."

    if query.get("sort") == "top_rated":
        sort_instruction = "The products are already sorted by rating. Recommend them in this exact order."

    history_block = _format_history(history)

    prompt =  f"""
You are the AI shopping assistant for our jewellery store. You are knowledgeable,
warm, and help customers find the perfect piece.

IMPORTANT RULES:

- Only recommend products listed below.
- Do NOT create, guess, or invent products.
- If a product is not listed, never mention it.
- Mention only the product name, price, stock, and rating exactly as provided.
- When you recommend a product, include its Product link so the customer can open it.
- Keep the response short, readable, and genuinely helpful (1-3 sentences).
- Do not use markdown bold formatting.
- If there are no matching products, say:
  "Sorry, I couldn't find a matching product."
- {sort_instruction}

MATERIAL / BRAND FACTS (critical — never violate):
- Zyraluxe sells ONLY imitation / fashion / costume jewellery. We do NOT sell solid gold, 14k/18k/22k gold, real silver, or certified diamonds.
- When a customer says "gold", understand it as GOLD-PLATED / gold-finish imitation. When they say "silver", understand it as OXIDISED / GERMAN SILVER or rhodium-plated imitation.
- Never say "14k gold", "solid gold", "real gold/silver", "sterling", or imply genuine precious metals. Always describe pieces as plated / oxidised / imitation / fashion jewellery.
- If a customer asks for "real gold/silver", politely clarify we are a budget fashion-jewellery brand (alloy gold-plated, oxidised/german silver, rhodium-plated, pearl, AD, kundan, beads, stones) — NOT solid precious metals.

RECENT CONVERSATION (for context only — reply to the latest Customer question):
{history_block}

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
        data = _post(payload, timeout=60)
        return data["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        return f"Sorry, I'm having trouble reaching the AI service right now. Please try again in a moment. ({e})"

    except KeyError:
        return "Unexpected response received from OpenRouter."


def ask_conversation(user_message, intent="general", filters=None, history=None):
    """
    Generate a free-form, natural reply for non-product turns
    (greetings, thanks, small talk, policy/FAQ questions, and
    filter-collection prompts) using the LLM so the wording is dynamic
    and on-brand instead of hardcoded. Falls back to a safe static
    string if the API fails.
    """

    filters = filters or {}
    history = history or []

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

 RECENT CONVERSATION (context only):
{_format_history(history)}

 Rules:
- Reply like a real human sales assistant, 1-2 short sentences.
- If intent is "greeting", welcome them and ask what jewellery they want (necklace, earrings, ring, jhumka, bangle, pendant, etc).
- If intent is "thanks", thank them warmly and invite them back.
- If the shopper just said they have no preference (e.g. "any", "doesn't matter"), acknowledge it briefly and move on.
- If we still need a budget, ask for a price range naturally (e.g. under Rs.500, under Rs.1000) and offer "any" as an option.
- If we still need a rating, ask for a minimum rating naturally (e.g. 4 star and above) and offer "any" as an option.
- Do NOT recommend specific products here. Do NOT use markdown. Keep it short.
- When the shopper mentions "gold" or "silver", treat it as GOLD-PLATED or OXIDISED/GERMAN SILVER imitation finish — never as solid precious metal.

 KNOWLEDGE BASE (use this to answer store policy, shipping, returns, sizing,
 care, materials, and FAQ questions accurately):
{kb_block}
- If the question is about store policy/shipping/returns/materials/care/FAQ and the KNOWLEDGE BASE above has relevant info, answer ONLY from it, concisely and accurately. Quote the real numbers (e.g. return window, free-shipping threshold, prices) EXACTLY as written — never guess or change a figure.
- If the KNOWLEDGE BASE does NOT contain the answer, say you're not sure and give the contact email zyraluxeofficial@gmail.com. NEVER invent policy details, prices, thresholds, or timelines.
- When asked whether items are real gold/diamond/silver or what materials you use, answer directly from the KNOWLEDGE BASE (Zyraluxe sells ONLY imitation/fashion jewellery — alloy gold-plated, oxidised/german silver, rhodium-plated, pearl, AD, kundan, beads, stones — NOT solid gold or certified diamonds). Never say "14k gold", "solid gold", or "real silver".
- Do NOT invent details, prices, policies, or products that are not in the KNOWLEDGE BASE or the product list. If the answer is not in the provided context, say you are not sure and suggest emailing zyraluxeofficial@gmail.com.
- Keep replies short (1-3 sentences) and friendly. Do NOT use markdown.
 """

    if not OPENROUTER_API_KEY:
        return kb_context or _missing_key()

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
        data = _post(payload, timeout=30)
        return data["choices"][0]["message"]["content"].strip()

    except Exception:
        # Safe static fallbacks so the bot never breaks if the LLM is down.
        # If we have knowledge-base content, answer straight from it.
        if kb_context:
            return kb_context.strip().split("\n\n")[0][:400]

        if intent == "greeting":
            return "Hello! Welcome to Zyraluxe. What kind of jewellery are you looking for today?"
        if intent == "thanks":
            return "You're welcome. I'm here whenever you want help choosing jewellery."
        if filters.get("budget") is None:
            return "Sure. What price range should I keep in mind? For example: under Rs.500, under Rs.1000, or say any."
        if filters.get("min_rating") is None:
            return "Got it. Do you want a minimum rating? For example: 4 star and above, 5 star, or say any."
        return "I can help you find jewellery step by step. Tell me the product or style you want, like necklace, earrings, jhumka, ring, or pearl set."
