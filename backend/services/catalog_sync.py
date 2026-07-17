import os

from services.woocommerce import get_all_products
from services.rag import _KNOWLEDGE_DIR

CATALOG_FILE = os.path.join(_KNOWLEDGE_DIR, "catalog.txt")


def build_catalog_text():
    """Pull the live product list and render it as plain text for the
    knowledge base. Returns the text and how many products were included."""
    try:
        products = get_all_products()
    except Exception as exc:
        return f"[catalog unavailable: {exc}]", 0

    if not isinstance(products, list):
        return "[catalog unavailable]", 0

    lines = [
        "Zyraluxe — Live Product Catalogue (from the store)",
        "",
    ]

    included = 0
    for p in products:
        name = (p.get("name") or "").strip()
        if not name:
            continue

        price = p.get("price") or p.get("regular_price") or ""
        status = p.get("stock_status") or ""
        categories = ", ".join(
            c.get("name", "") for c in p.get("categories", []) if c.get("name")
        )
        permalink = p.get("permalink") or ""

        line = f"- {name}"
        if categories:
            line += f" (category: {categories})"
        if price:
            line += f" | Price: Rs.{price}"
        if status:
            line += f" | {status}"
        if permalink:
            line += f" | link: {permalink}"
        lines.append(line)
        included += 1

    lines.append("")
    lines.append(
        "Note: prices and availability change often. Always confirm the "
        "current price/stock on the product link before promising a customer."
    )
    return "\n".join(lines), included


def sync_catalog():
    """Refresh knowledge/catalog.txt from the live store. Safe to call at
    startup — any failure is swallowed so the bot still runs."""
    try:
        text, count = build_catalog_text()
        with open(CATALOG_FILE, "w", encoding="utf-8") as fh:
            fh.write(text)
        return count
    except Exception:
        return 0


if __name__ == "__main__":
    n = sync_catalog()
    print(f"Synced {n} products to {CATALOG_FILE}")
