def product_rating(product):

    try:
        return float(product.get("average_rating") or 0)
    except (TypeError, ValueError):
        return 0


def product_sales(product):

    try:
        return int(product.get("total_sales") or 0)
    except (TypeError, ValueError):
        return 0


def score_product(product, query):
    """
    Give a relevance score to a product.
    Higher score = better match.
    """

    score = 0

    name = product.get("name", "").lower()
    description = product.get("short_description", "").lower()

    category = ""

    if product.get("categories"):
        category = " ".join(
            c["name"].lower()
            for c in product["categories"]
        )

    text = (name + " " + description + " " + category)

    from utils.filters import _matches_category

    # Category (strongest signal). Reward a real category match heavily and
    # penalize products that belong to a different category so the bot never
    # shows necklaces when the shopper asked for earrings.
    if query.get("category"):
        if _matches_category(text, query["category"]):
            score += 10
            if query["category"] in category:
                score += 3
            if query["category"] in name:
                score += 2
        else:
            score -= 12

    # Material
    if query.get("material"):

        if query["material"] in name:
            score += 5

        if query["material"] in description:
            score += 4

        if query["material"] in category:
            score += 2

    # Budget

    try:

        price = float(product["price"])

        if query.get("budget"):

            if price <= query["budget"]:
                score += 5

            else:
                score -= 5

    except:

        pass

    return score


def rank_products(products, query, limit=3):

    sort_mode = query.get("sort")

    if sort_mode == "best_selling":
        ranked = sorted(
            products,
            key=lambda p: (product_sales(p), product_rating(p), score_product(p, query)),
            reverse=True
        )

        return ranked[:limit]

    if sort_mode == "top_rated":
        ranked = sorted(
            products,
            key=lambda p: (product_rating(p), product_sales(p), score_product(p, query)),
            reverse=True
        )

        return ranked[:limit]

    ranked = sorted(

        products,

        key=lambda p: score_product(p, query),

        reverse=True

    )

    return ranked[:limit]
