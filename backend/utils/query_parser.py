import re

# Real store categories (from zyraluxe.in product categories). Each entry is
# mapped to a canonical singular form used downstream for filtering/ranking.
CATEGORY_ALIASES = {
    "earring": ["earring", "earrings", "jhumka", "jhumkas", "jhumki", "jhumkis",
                "jhumka earring", "chandbali", "chandbalis", "dangler", "danglers",
                "stud", "studs", "hoop", "hoops", "drop earring"],
    "pendant": ["pendant", "pendants", "pendent", "pendents", "pendant necklace",
                "locket", "lockets"],
    "necklace": ["necklace", "necklaces", "sitahar", "sitahars", "chain", "chains",
                 "neck piece", "necklace set", "neck set"],
    "choker": ["choker", "chokers", "chokker", "chokkers", "collar necklace"],
    "oxidised jhumka": ["oxidised jhumka", "oxidized jhumka", "oxidised jhumka earring",
                         "oxide jhumka"],
    "anklet": ["anklet", "anklets", "payal", "payal set", "ankle bracelet"],
    "bangle": ["bangle", "bangles", "kada", "kadas", "bangle set"],
    "bracelet": ["bracelet", "bracelets", "wrist band", "wristband"],
    "combo": ["combo", "combos", "combo pack", "combo set", "pack of", "set of",
               "pair of", "4 pair", "4 pairs", "jewellery set", "jewelry set",
               "jewellery sets", "jewelry sets"],
}

# Materials as the store describes them. "american diamond" is an accent type,
# not a precious stone, so keep it under imitation finishes.
MATERIALS = [
    "american diamond",
    "austrian diamond",
    "oxidized",
    "oxidised",
    "diamond",
    "silver",
    "german silver",
    "kundan",
    "pearl",
    "gold",
    "rhodium",
    "beads",
    "stone",
    "enamel",
    "mehendi",
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

MORE_TERMS = [
    "more",
    "more products",
    "show more",
    "see more",
    "load more",
    "another",
    "others",
    "other products",
    "more items",
    "more options",
    "next",
    "next page",
    "additional",
    "anything else",
    "what else",
    "more results",
    "view more"
]

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
        "min_rating": None,
        "more": False
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

    # "show more" / "more products" — only meaningful when the client echoes
    # back the previous search query via context (handled in routes.py).
    if any(term in query for term in MORE_TERMS) and len(query.split()) <= 4:
        result["more"] = True
        result["intent"] = "shopping"
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

    budget = re.search(r"(?:under|below|budget|price|rs\.?|₹|rupees)\s*(\d+)|(\d+)\s*(?:rs|₹|rupees)", query)

    if budget and not rating_match:
        result["budget"] = int(budget.group(1) or budget.group(2))

    # Combo / set packs ("combo", "pack of 4", "set of 2") take priority over a
    # single-piece category so we don't mislabel a 4-pair earring pack as just
    # "earring" (and a stray "4" never becomes a budget).
    combo_aliases = CATEGORY_ALIASES["combo"]
    if any(re.search(r"\b" + re.escape(a) + r"\b", query) for a in combo_aliases):
        result["category"] = "combo"
    else:
        for canonical, aliases in CATEGORY_ALIASES.items():
            if canonical == "combo":
                continue
            if any(re.search(r"\b" + re.escape(a) + r"\b", query) for a in aliases):
                result["category"] = canonical
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


# Phrases that mean "continue / refine the previous search" rather than start
# a brand-new one. Used to decide whether to merge with the previous query.
_REFINE_TERMS = [
    "cheaper", "less expensive", "lower price", "more affordable", "budget",
    "expensive", "pricier", "higher", "costlier",
    "in silver", "in gold", "silver", "gold", "rose gold", "oxidized",
    "under", "below", "above", "over", "within",
    "more", "another", "others", "other", "different", "similar",
    "show me", "show", "see", "those", "these", "that", "them",
    "rating", "rated", "star", "stars",
]


def merge_with_history(query, prev_query, message=""):
    """
    Carry over context from the previous turn so the conversation feels
    continuous. If the new message is a short follow-up that doesn't restate
    the product type, we inherit the previous category/material/budget/rating
    instead of dropping them.

    `query` is the freshly parsed current message; `prev_query` is the last
    executed search (or None). Returns the merged query dict.
    """
    if not prev_query:
        return query

    merged = dict(query)

    # A follow-up is a short message that doesn't restate a concrete product
    # (no category, no material, no sort) but contains refine language.
    text = (message or "").strip().lower()
    has_concrete_focus = any([
        merged.get("category"),
        merged.get("material"),
        merged.get("sort"),
    ])
    looks_like_followup = (
        (
            not has_concrete_focus
            and (len(text.split()) <= 6)
            and any(term in text for term in _REFINE_TERMS)
        )
        or merged.get("more")
        or (not has_concrete_focus and prev_query and len(text.split()) <= 3)
    )

    if looks_like_followup:
        # Inherit what the user didn't re-specify this turn.
        for key in ("category", "material", "budget", "min_rating", "sort"):
            if merged.get(key) in (None, ""):
                merged[key] = prev_query.get(key)

        # The current message is refine language, not a product name, so don't
        # carry a stale keyword that would wrongly filter the results.
        if merged.get("keyword"):
            merged["keyword"] = None

        # Keep shopping intent so follow-ups search instead of small-talking.
        if prev_query.get("intent") == "shopping":
            merged["intent"] = "shopping"

    return merged


