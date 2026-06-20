"""Lokalni embedding modul — tekst NE napusta infrastrukturu.

Model: intfloat/multilingual-e5-base (768 dim), jak za srpski (Latn+Cyrl).
e5 konvencija: dokumenti se prefiksuju sa "passage: ", upiti sa "query: ".

Model se ucitava lenjivo (prvi poziv) i kesira u procesu (worker drzi instancu).
"""
import logging
from typing import List, Optional

from config import settings

logger = logging.getLogger(__name__)

_model = None  # lazy singleton


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Ucitavam embedding model: %s", settings.EMBEDDING_MODEL)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def embed_texts(texts: List[str], is_query: bool = False) -> List[List[float]]:
    """Vraca listu embedding vektora (dimenzija EMBEDDING_DIM) za listu tekstova.

    is_query: True za upit (npr. 'slicni clanci' za jedan clanak), False za dokumente.
    Normalizovani vektori (cosine == dot product).
    """
    if not texts:
        return []
    prefix = "query: " if is_query else "passage: "
    model = _get_model()
    vecs = model.encode(
        [prefix + (t or "") for t in texts],
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=32,
    )
    return [v.tolist() for v in vecs]


def embed_one(text: str, is_query: bool = False) -> Optional[List[float]]:
    out = embed_texts([text], is_query=is_query)
    return out[0] if out else None


def build_embed_input(title: str, text_content: Optional[str]) -> str:
    """Ulaz za embedding: naslov + pocetak teksta (dovoljno za semanticku slicnost)."""
    title = (title or "").strip()
    body = (text_content or "").strip()[: settings.EMBEDDING_TEXT_CHARS]
    return f"{title}. {body}".strip()
