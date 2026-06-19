"""
Priprema teksta clanaka za AI analizu.
"""

MAX_TEXT_WORDS = 3000
MAX_TITLE_CHARS = 300
MAX_SUBTITLE_CHARS = 200


def prepare_article(article: dict) -> dict:
    """
    Priprema clanak za slanje AI-ju.
    Trunkuje preduge tekstove (Informer, Radar imaju 10k+ znakova).
    """
    title = (article.get("title") or "")[:MAX_TITLE_CHARS]
    subtitle = (article.get("subtitle") or "")[:MAX_SUBTITLE_CHARS] or None

    text_raw = article.get("text_content") or ""
    words = text_raw.split()
    if len(words) > MAX_TEXT_WORDS:
        text = " ".join(words[:MAX_TEXT_WORDS]) + "... [tekst trunkovan]"
        truncated = True
    else:
        text = text_raw
        truncated = False

    return {
        "article_id": article.get("id") or article.get("article_id"),
        "source_id": article["source_id"],
        "title": title,
        "subtitle": subtitle,
        "text": text,
        "category": article.get("category"),
        "published_at": article.get("published_at"),
        "truncated": truncated,
        "word_count": len(words),
    }
