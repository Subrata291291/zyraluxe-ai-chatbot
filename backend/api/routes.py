import os

from fastapi import APIRouter
from html import unescape
from html.parser import HTMLParser

from services.ranking import rank_products
from models.schemas import ChatRequest, ChatResponse, Product
from utils.query_parser import parse_query, merge_with_history
from utils.filters import filter_products
from services.woocommerce import get_all_products
from ai import ask_ai, ask_conversation
from services.rag import get_knowledge_context
from services.catalog_sync import sync_catalog

router = APIRouter()


@router.post("/sync-catalog")
def sync_catalog_endpoint(token: str = ""):
    # Light guard so the endpoint isn't abused publicly.
    expected = os.getenv("SYNC_TOKEN", "")
    if expected and token != expected:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Forbidden")
    count = sync_catalog()
    return {"synced": count}

# Keywords that signal a store-policy / FAQ question rather than a product hunt.
_KB_TRIGGER_TERMS = [
    "ship", "shipping", "deliver", "delivery", "cod", "cash on delivery",
    "return", "returns", "refund", "exchange", "replace", "warranty",
    "size", "sizing", "resize", "ring size", "measurement",
    "care", "clean", "polish", "tarnish", "storage",
    "custom", "engrav", "gift", "gifting", "gift wrap",
    "payment", "pay", "upi", "card", "track", "tracking",
    "certif", "hallmark", "about", "who are you", "company",
    "guide", "gold", "diamond", "lab grown", "lab-grown",
    "sell", "selling", "collection", "catalogue", "catalog",
    "what do you have", "what do you offer", "tell me about",
    "jewellery do you", "types of",
]


def is_knowledge_query(message, query):
    """True when the message is likely a policy/FAQ question we can answer
    from the knowledge base, and not a focused product request."""
    if not get_knowledge_context(message):
        return False
    text = message.strip().lower()
    if any(term in text for term in _KB_TRIGGER_TERMS):
        # Sizing questions (ring size, resize, measurement) are always KB,
        # even though "ring" is also a product category.
        if any(s in text for s in ("size", "sizing", "resize", "measurement", "measure")):
            return True
        # Informational material questions ("are your products real gold?",
        # "do you sell silver?") are KB, even if a material was detected.
        if any(p in text for p in (
            "real", "genuine", "solid", "certif", "authentic",
            "do you sell", "do you make", "made of", "what kind of",
            "what type of", "what are", "type of jewellery",
        )):
            return True
        # Otherwise treat as KB only when there's no clear product
        # category/material intent, so "show me gold necklaces" still searches.
        if not query.get("category") and not query.get("material"):
            return True
    return False


class DescriptionTextParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"img", "source"}:
            return

        if tag in {"picture", "figure", "video", "iframe", "script", "style"}:
            self.skip_depth += 1

    def handle_startendtag(self, tag, attrs):
        if tag in {"img", "source"}:
            return

    def handle_endtag(self, tag):
        if self.skip_depth and tag in {"picture", "figure", "video", "iframe", "script", "style"}:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


def conversation_reply(message, query, history=None):

    intent = query.get("intent")
    return ask_conversation(message, intent or "general", query, history)


def clean_description(description):

    parser = DescriptionTextParser()
    parser.feed(unescape(description or ""))

    return " ".join(
        " ".join(parser.parts).split()
    )


def wants_no_preference(message):

    text = message.strip().lower()

    return text in {"any", "anything", "no", "no preference", "skip", "doesn't matter", "doesnt matter"}


def should_collect_filters(query):

    has_product_focus = any([
        query.get("category"),
        query.get("material"),
        query.get("keyword")
    ])

    if query.get("sort"):
        return False

    return has_product_focus and (query.get("budget") is None or query.get("min_rating") is None)


def next_filter_question(filters):

    # Dynamic, AI-generated follow-up based on what's still missing.
    if filters.get("budget") is None and not filters.get("skip_budget"):
        return ask_conversation("What price range should I keep in mind?", "filter_budget", filters)

    if filters.get("min_rating") is None and not filters.get("skip_rating"):
        return ask_conversation("Do you want a minimum rating?", "filter_rating", filters)

    return None


def build_context_response(reply, query, context):

    return ChatResponse(
        reply=reply,
        total_products=0,
        query=query,
        products=[],
        context=context
    )


def product_cards_from_products(products):

    product_cards = []

    for product in products:

        image = ""

        if product.get("images"):
            image = product["images"][0]["src"]

        product_cards.append(

            Product(

                id=product["id"],

                name=product["name"],

                price=product["price"],

                image=image,

                url=product["permalink"],

                stock=product.get("stock_status", ""),

                category=", ".join(
                    c["name"] for c in product.get("categories", [])
                ),

                description=clean_description(
                    product.get("short_description", "")
                ),

                rating=product.get("average_rating", "0"),

                rating_count=product.get("rating_count", 0)

            )

        )

    return product_cards


def run_product_search(message, query, limit=3, history=None):

    products = get_all_products()
    matched_products = filter_products(products, query)
    matched_products = rank_products(
        matched_products,
        query,
        limit=limit
    )
    answer = ask_ai(message, matched_products, query, history)
    product_cards = product_cards_from_products(matched_products)

    context = {"last_query": query, "last_limit": limit}

    return ChatResponse(
        reply=answer,
        total_products=len(product_cards),
        query=query,
        products=product_cards,
        context=context
    )


def run_more_products(message, query, limit, seen_ids, history=None):
    """
    "Show more" handler. Returns up to `limit` products for the previous
    search, skipping ones already shown. If the strict filter is exhausted,
    progressively relaxes constraints (budget -> rating -> material) to keep
    surfacing *related* products in the same category instead of repeating.
    """
    products = get_all_products()
    seen = set(seen_ids or [])

    # 1) Strict matches not yet shown.
    strict = [p for p in filter_products(products, query) if p.get("id") not in seen]
    strict = rank_products(strict, query, limit=limit)

    if len(strict) >= limit:
        chosen = strict[:limit]
    else:
        # 2) Need more — relax filters step by step to find related items.
        needed = limit - len(strict)
        relaxed_pool = [p for p in products if p.get("id") not in seen
                        and p.get("id") not in {p2.get("id") for p2 in strict}]

        # Drop budget + rating first (keep category/material context).
        r1 = _relax(query, drop=["budget", "min_rating"])
        extra = [p for p in filter_products(relaxed_pool, r1) if p.get("id") not in seen]
        extra = rank_products(extra, r1, limit=needed)

        if len(extra) < needed:
            # Still short — also drop material (same category, any material).
            r2 = _relax(query, drop=["budget", "min_rating", "material"])
            more = [p for p in filter_products(relaxed_pool, r2) if p.get("id") not in seen
                    and p.get("id") not in {p3.get("id") for p3 in extra}]
            extra += rank_products(more, r2, limit=needed - len(extra))

        chosen = strict + extra[:needed]

    answer = ask_ai(message, chosen, query, history)
    product_cards = product_cards_from_products(chosen)

    context = {"last_query": query, "last_limit": limit}

    return ChatResponse(
        reply=answer,
        total_products=len(product_cards),
        query=query,
        products=product_cards,
        context=context
    )


def _relax(query, drop):
    """Return a copy of the query with the given keys cleared."""
    relaxed = dict(query)
    for key in drop:
        relaxed[key] = None
    return relaxed


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    context = request.context or {}
    history = context.get("history") or []

    # Parse the new message, then merge with the previous search so follow-ups
    # ("cheaper ones", "any in silver?", "more") keep the earlier context.
    raw_query = parse_query(request.message)
    prev_query = context.get("last_query")
    query = merge_with_history(raw_query, prev_query, request.message)

    # "More" — surface additional related products, skipping ones already shown.
    if query.get("more") and prev_query:
        prev_limit = int(context.get("last_limit", 3) or 3)
        seen_ids = context.get("seen_ids") or []
        result = run_more_products(
            request.message, prev_query, limit=prev_limit + 3,
            seen_ids=seen_ids, history=history
        )
        result.context = _update_context(context, result, request.message, result.reply)
        return result

    if context.get("mode") == "collect_filters":
        filters = context.get("filters", {})
        answer_query = parse_query(request.message)

        if context.get("step") == "budget":
            if wants_no_preference(request.message):
                filters["skip_budget"] = True
            elif answer_query.get("budget") is not None:
                filters["budget"] = answer_query["budget"]
            else:
                resp = build_context_response(
                    ask_conversation(request.message, "filter_budget", filters, history),
                    filters,
                    context
                )
                resp.context = _update_context(context, resp, request.message, resp.reply)
                return resp

        if context.get("step") == "rating":
            if wants_no_preference(request.message):
                filters["skip_rating"] = True
            elif answer_query.get("min_rating") is not None:
                filters["min_rating"] = answer_query["min_rating"]
            else:
                resp = build_context_response(
                    ask_conversation(request.message, "filter_rating", filters, history),
                    filters,
                    context
                )
                resp.context = _update_context(context, resp, request.message, resp.reply)
                return resp

        question = next_filter_question(filters)

        if question:
            next_step = "budget" if filters.get("budget") is None and not filters.get("skip_budget") else "rating"
            return build_context_response(
                question,
                filters,
                {
                    "mode": "collect_filters",
                    "step": next_step,
                    "filters": filters
                }
            )

        filters["intent"] = "shopping"
        filters.pop("skip_budget", None)
        filters.pop("skip_rating", None)

        result = run_product_search(request.message, filters, history=history)
        result.context = _update_context(context, result, request.message, result.reply)
        return result

    if query.get("intent") != "shopping":
        resp = ChatResponse(
            reply=conversation_reply(request.message, query, history),
            total_products=0,
            query=query,
            products=[],
            context={}
        )
        resp.context = _update_context(context, resp, request.message, resp.reply)
        return resp

    # Knowledge-base first: policy/FAQ questions get grounded answers from
    # the knowledge base instead of being run as a product search.
    if is_knowledge_query(request.message, query):
        resp = ChatResponse(
            reply=conversation_reply(request.message, query, history),
            total_products=0,
            query=query,
            products=[],
            context={}
        )
        resp.context = _update_context(context, resp, request.message, resp.reply)
        return resp

    if should_collect_filters(query):
        question = next_filter_question(query)
        step = "budget" if query.get("budget") is None else "rating"

        return build_context_response(
            question,
            query,
            {
                "mode": "collect_filters",
                "step": step,
                "filters": query
            }
        )

    result = run_product_search(request.message, query, history=history)
    result.context = _update_context(context, result, request.message, result.reply)
    return result


def _update_context(context, response, user_message, assistant_reply):
    """
    Attach rolling conversation memory (history + last search) to the response
    context so the next turn can continue naturally.
    """
    history = list(context.get("history") or [])
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": assistant_reply})
    # Keep the last ~10 turns to bound payload size.
    history = history[-10:]

    new_context = dict(response.context or {})
    new_context["history"] = history
    if response.products:
        # Remember the search so follow-ups can refine it.
        new_context["last_query"] = response.query
        new_context["last_limit"] = int(new_context.get("last_limit", 3) or 3)
        # Track shown product ids so "more" never repeats them.
        shown = list(context.get("seen_ids") or [])
        shown += [p.id for p in response.products]
        # De-duplicate while preserving order.
        seen_unique = []
        for pid in shown:
            if pid not in seen_unique:
                seen_unique.append(pid)
        new_context["seen_ids"] = seen_unique
    return new_context
