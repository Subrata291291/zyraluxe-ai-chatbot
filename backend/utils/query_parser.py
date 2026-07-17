import re

CATEGORIES = [
    "american diamond",
    "necklaces",
    "necklace",
    "earrings",
    "earring",
    "bracelet",
    "pendant",
    "jhumka",
    "bangle",
    "choker",
    "rings",
    "ring",
    "chain"
]

MATERIALS = [
    "american diamond",
    "oxidized",
    "diamond",
    "silver",
    "kundan",
    "pearl",
    "gold"
]

BEST_SELLING_TERMS = [
    "best selling",
    "best-selling",
    "bestselling",
    "best seller",
    "best sellers",
    "most sold",
    "popular items",
    "popular products"
]

TOP_RATED_TERMS = [
    "top rated",
    "top-rated",
    "highest rated",
    "best rated"
]

GREETING_TERMS = {
    "hi",
    "hii",
    "hello",
    "hey",
    "heyy",
    "good morning",
    "good afternoon",
    "good evening",
    "namaste"
}

THANKS_TERMS = {
    "thanks",
    "thank you",
    "thx",
    "ok thanks",
    "okay thanks"
}

CASUAL_STARTS = (
    "how are",
    "what are you",
    "who are you",
    "can you help",
    "help me",
    "tell me about yourself"
)

SHOPPING_TERMS = [
    "show",
    "find",
    "search",
    "recommend",
    "suggest",
    "want",
    "need",
    "buy",
    "shop",
    "item",
    "items",
    "product",
    "products",
    "under",
    "below",
    "price",
    "budget",
    "rating",
    "rated",
    "star",
    "stars"
]

STOP_WORDS_PATTERN = r"\b(show|find|search|recommend|suggest|want|need|buy|shop|items?|products?|please|me|some|any|with|for|the|a|an)\b"


def parse_query(query):

    original_query = query.strip().lower()
    query = original_query

    result = {
        "budget": None,
        "category": None,
        "material": None,
        "sort": None,
        "intent": "shopping",
        "keyword": None,
        "min_rating": None
    }

    if query in GREETING_TERMS:
        result["intent"] = "greeting"
        return result

    if query in THANKS_TERMS:
        result["intent"] = "thanks"
        return result

    if any(query.startswith(start) for start in CASUAL_STARTS):
        result["intent"] = "conversation"
        return result

    if any(term in query for term in BEST_SELLING_TERMS):
        result["sort"] = "best_selling"

    if any(term in query for term in TOP_RATED_TERMS):
        result["sort"] = "top_rated"

    rating_match = re.search(
        r"(?:rating|rated|star|stars)\s*([1-5](?:\.\d)?)|([1-5](?:\.\d)?)\s*(?:\+|and above|above)?\s*(?:star|stars|rating|rated)",
        query
    )

    if rating_match:
        result["min_rating"] = float(rating_match.group(1) or rating_match.group(2))

    budget = re.search(r"(?:under|below|budget|price|rs\.?|₹)\s*(\d+)|(\d+)\s*(?:rs|₹|rupees)?", query)

    if budget and not rating_match:
        result["budget"] = int(budget.group(1) or budget.group(2))

    for cat in CATEGORIES:
        if re.search(r"\b" + re.escape(cat) + r"\b", query):
            result["category"] = cat.rstrip("s") if cat.endswith("s") else cat
            break

    for mat in MATERIALS:
        if re.search(r"\b" + re.escape(mat) + r"\b", query):
            result["material"] = mat
            break

    has_shopping_signal = any([
        result["budget"],
        result["category"],
        result["material"],
        result["sort"],
        result["min_rating"],
        any(term in query for term in SHOPPING_TERMS)
    ])

    if result["intent"] == "shopping" and not result["category"] and not result["material"] and not result["sort"]:
        cleaned_keyword = re.sub(STOP_WORDS_PATTERN, "", query)
        cleaned_keyword = " ".join(cleaned_keyword.split())
        result["keyword"] = cleaned_keyword or None

    if not has_shopping_signal:
        if result["keyword"] and len(result["keyword"].split()) >= 2:
            result["intent"] = "shopping"
        else:
            result["intent"] = "conversation"

    return result


