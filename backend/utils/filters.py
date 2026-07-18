import re

# Reverse lookup: canonical store category -> keywords that identify it in a
# product's text (name + WooCommerce category names). Using word boundaries
# avoids false matches like "ring" inside "earring".
CATEGORY_KEYWORDS = {
    "earring": ["earring", "earrings", "jhumka", "jhumki", "jhumkas",
                 "chandbali", "chandbalis", "dangler", "danglers", "stud",
                 "studs", "hoop", "hoops"],
    "pendant": ["pendant", "pendants", "pendent", "pendents", "locket", "lockets"],
    "necklace": ["necklace", "necklaces", "sitahar", "sitahars", "neck piece",
                  "neck set", "necklace set"],
    "choker": ["choker", "chokers", "chokker", "chokkers"],
    "oxidised jhumka": ["oxidised jhumka", "oxidized jhumka", "oxide jhumka"],
    "anklet": ["anklet", "anklets", "payal"],
    "bangle": ["bangle", "bangles", "kada", "kadas"],
    "bracelet": ["bracelet", "bracelets"],
    "combo": ["combo", "combos", "jewellery set", "jewelry set", "pack of",
               "set of", "pair of"],
}


def _matches_category(text, canonical):
    keywords = CATEGORY_KEYWORDS.get(canonical, [canonical])
    return any(re.search(r"\b" + re.escape(k) + r"\b", text) for k in keywords)


def product_rating(product):
    try:
        return float(product.get("average_rating") or 0)
    except (TypeError, ValueError):
        return 0


def filter_products(products, query):
    results = []

    for product in products:
        try:
            price = float(product["price"])
        except:
            continue

        # Budget filter
        if query.get("budget"):
            if price > query["budget"]:
                continue

        if query.get("min_rating"):
            if product_rating(product) < float(query["min_rating"]):
                continue

        # Category / material / keyword filter
        text = (
            product.get("name", "") + " " +
            product.get("short_description", "") + " " +
            " ".join(c.get("name", "") for c in product.get("categories", []))
        ).lower()

        if query.get("category"):
            if not _matches_category(text, query["category"]):
                continue

        if query.get("material"):
            if query["material"] not in text:
                continue

        if query.get("keyword"):
            if query["keyword"] not in text:
                continue

        results.append(product)

    return results
