import os

from fastapi import APIRouter
from html import unescape
from html.parser import HTMLParser

from services.ranking import rank_products
from models.schemas import ChatRequest, ChatResponse, Product
from utils.query_parser import parse_query
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


def conversation_reply(message, query):

    intent = query.get("intent")
    return ask_conversation(message, intent or "general", query)


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


def run_product_search(message, query):

    products = get_all_products()
    matched_products = filter_products(products, query)
    matched_products = rank_products(
        matched_products,
        query
    )
    answer = ask_ai(message, matched_products, query)
    product_cards = product_cards_from_products(matched_products)

    return ChatResponse(
        reply=answer,
        total_products=len(product_cards),
        query=query,
        products=product_cards,
        context={}
    )


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    query = parse_query(request.message)
    context = request.context or {}

    if context.get("mode") == "collect_filters":
        filters = context.get("filters", {})
        answer_query = parse_query(request.message)

        if context.get("step") == "budget":
            if wants_no_preference(request.message):
                filters["skip_budget"] = True
            elif answer_query.get("budget") is not None:
                filters["budget"] = answer_query["budget"]
            else:
                return build_context_response(
                    ask_conversation(request.message, "filter_budget", filters),
                    filters,
                    context
                )

        if context.get("step") == "rating":
            if wants_no_preference(request.message):
                filters["skip_rating"] = True
            elif answer_query.get("min_rating") is not None:
                filters["min_rating"] = answer_query["min_rating"]
            else:
                return build_context_response(
                    ask_conversation(request.message, "filter_rating", filters),
                    filters,
                    context
                )

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

        return run_product_search(request.message, filters)

    if query.get("intent") != "shopping":
        return ChatResponse(
            reply=conversation_reply(request.message, query),
            total_products=0,
            query=query,
            products=[],
            context={}
        )

    # Knowledge-base first: policy/FAQ questions get grounded answers from
    # the knowledge base instead of being run as a product search.
    if is_knowledge_query(request.message, query):
        return ChatResponse(
            reply=conversation_reply(request.message, query),
            total_products=0,
            query=query,
            products=[],
            context={}
        )

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

    return run_product_search(request.message, query)
