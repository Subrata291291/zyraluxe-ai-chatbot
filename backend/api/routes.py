from fastapi import APIRouter
from html import unescape
from html.parser import HTMLParser

from backend.services.ranking import rank_products
from backend.models.schemas import ChatRequest, ChatResponse, Product
from backend.utils.query_parser import parse_query
from backend.utils.filters import filter_products
from backend.services.woocommerce import get_all_products
from backend.services.ai import ask_ai

router = APIRouter()


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


def conversation_reply(query):

    intent = query.get("intent")

    if intent == "greeting":
        return "Hello! Welcome to Zyraluxe. What kind of jewellery are you looking for today?"

    if intent == "thanks":
        return "You're welcome. I am here whenever you want help choosing jewellery."

    return "I can help you find jewellery step by step. Tell me the product or style you want, like necklace, earrings, jhumka, ring, or pearl set."


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

    if filters.get("budget") is None and not filters.get("skip_budget"):
        return "Sure. What price range should I keep in mind? For example: under Rs.500, under Rs.1000, or say any."

    if filters.get("min_rating") is None and not filters.get("skip_rating"):
        return "Got it. Do you want a minimum rating? For example: 4 star and above, 5 star, or say any."

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
                    "Please share a price range, like under Rs.500, or say any.",
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
                    "Please share a minimum rating, like 4 star and above, or say any.",
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
            reply=conversation_reply(query),
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
