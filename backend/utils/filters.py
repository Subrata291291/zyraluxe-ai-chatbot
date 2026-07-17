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

            if query["category"] not in text:
                continue

        if query.get("material"):

            if query["material"] not in text:
                continue

        if query.get("keyword"):

            if query["keyword"] not in text:
                continue

        results.append(product)

    return results
