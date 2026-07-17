import os
import re
from collections import Counter

# Knowledge base lives in the "knowledge" folder at the project root.
_KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "knowledge",
)

# Stopwords ignored during keyword scoring (kept small + English/Hindi-friendly)
_STOPWORDS = set("""
a an the and or but if then of to in on at for with without from by is are was were
be been being do does did have has had i you we they he she it my your our their this that
what when where which who how why can will would should could me us them as not no any
yes please thanks thank hi hello hey yo rs under above below between per into about
""".split())

_CHUNKS = None  # cached list of {"source": str, "text": str}


def _tokenize(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS and len(t) > 1]


def _load_chunks():
    """Read every .txt file in the knowledge folder and split into paragraphs."""
    global _CHUNKS
    if _CHUNKS is not None:
        return _CHUNKS

    chunks = []
    if not os.path.isdir(_KNOWLEDGE_DIR):
        return chunks

    for fname in sorted(os.listdir(_KNOWLEDGE_DIR)):
        if not fname.lower().endswith(".txt"):
            continue
        path = os.path.join(_KNOWLEDGE_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except Exception:
            continue

        source = os.path.splitext(fname)[0].replace("_", " ").title()
        # Split into paragraphs / Q&A blocks so retrieval is focused
        for block in re.split(r"\n\s*\n", raw):
            block = block.strip()
            if len(block) < 40:
                continue
            chunks.append({"source": source, "text": block})

    _CHUNKS = chunks
    return chunks


def search_knowledge(query, top_k=3, min_score=1):
    """
    Keyword-overlap search over the knowledge base.
    Returns a list of {source, text} chunks ranked by relevance.
    """
    chunks = _load_chunks()
    if not chunks:
        return []

    q_tokens = Counter(_tokenize(query))
    if not q_tokens:
        return []

    scored = []
    for chunk in chunks:
        c_tokens = Counter(_tokenize(chunk["text"]))
        # Score = number of query tokens found in the chunk (weighted)
        score = sum(count for tok, count in q_tokens.items() if tok in c_tokens)
        if score >= min_score:
            scored.append((score, chunk))

    # Higher score first; tie-break by shorter (more focused) chunk
    scored.sort(key=lambda x: (x[0], -len(x[1]["text"])), reverse=True)

    return [c for _, c in scored[:top_k]]


def get_knowledge_context(query, max_chars=1400):
    """Return a formatted knowledge block to inject into the AI prompt, or ''."""
    hits = search_knowledge(query, top_k=3)
    if not hits:
        return ""

    parts = []
    total = 0
    for hit in hits:
        block = f"[{hit['source']}]\n{hit['text']}"
        if total + len(block) > max_chars:
            # Trim the block to fit the budget
            remaining = max(0, max_chars - total)
            block = block[:remaining].rsplit(" ", 1)[0] + "..."
        parts.append(block)
        total += len(block)
        if total >= max_chars:
            break

    if not parts:
        return ""

    return "\n\n".join(parts)
