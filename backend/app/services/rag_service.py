from typing import Optional, Dict, Any
import re
import numpy as np

from app.core.config import settings
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.medical_document import MedicalDocument

# ------------------------------------------------------------------
# BACKWARD-COMPATIBLE RETURN OBJECT
# ------------------------------------------------------------------

class RAGResult(list):
    """
    Backward-compatible return type for retrieve_context().

    Supports BOTH:
      1) Legacy style: context = retrieve_context(...); context[0] is a string
      2) New style: chunks, conf = retrieve_context(...)

    Internally stores:
      - chunks: list[dict]
      - confidence: float
    """

    def __init__(self, chunks: list[dict], confidence: float):
        def _fmt(c):
            citation = c.get("citation") or {}
            src = citation.get("source") or ""
            content = c.get("content") or ""
            if src:
                return f"{src}: {content}"
            return content

        super().__init__([_fmt(c) for c in chunks])

        self.chunks = chunks
        self.confidence = confidence

    def __iter__(self):
        # When unpacking, return (chunks, confidence)
        yield self.chunks
        yield self.confidence


# ------------------------------------------------------------------
# BASIC UTILS
# ------------------------------------------------------------------

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    v1 = np.array(vec1, dtype=np.float32)
    v2 = np.array(vec2, dtype=np.float32)
    denom = (np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom == 0:
        return 0.0
    return float(np.dot(v1, v2) / denom)


def infer_query_intent(query: str) -> str:
    q = query.lower()
    if "symptom" in q or "sign" in q:
        return "symptoms"
    if "cause" in q:
        return "causes"
    if "treat" in q or "treatment" in q:
        return "treatment"
    return "general"


def any_keyword_filter(keywords: list[str]):
    """
    OR filter: match any keyword in title/content.
    Useful for multi-drug queries where no chunk contains all keywords.
    """
    if not keywords:
        return None

    return or_(
        *[
            or_(
                MedicalDocument.title.ilike(f"%{kw}%"),
                MedicalDocument.content.ilike(f"%{kw}%"),
            )
            for kw in keywords
        ]
    )


def mandatory_keyword_filter(mandatory: list[str]):
    if not mandatory:
        return None

    return and_(
        *[
            or_(
                MedicalDocument.title.ilike(f"%{kw}%"),
                MedicalDocument.content.ilike(f"%{kw}%"),
            )
            for kw in mandatory
        ]
    )


def _normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _clean_med_terms(terms: list[str]) -> list[str]:
    bad = {
        "take", "with", "together", "combine", "medicine", "drug",
        "dose", "dosage", "tablet", "side", "effect", "effects",
        "interaction", "can", "should", "missed", "safe"
    }
    out = []
    for t in terms:
        t = _normalize_text(t)
        if not t or len(t) < 3:
            continue
        if t in bad:
            continue
        out.append(t)
    # unique preserve order
    seen = set()
    uniq = []
    for x in out:
        if x not in seen:
            uniq.append(x)
            seen.add(x)
    return uniq


def looks_like_medication_query(query: str) -> bool:
    q = _normalize_text(query)

    med_markers = [
        "take",
        "tablet",
        "medicine",
        "drug",
        "dose",
        "dosage",
        "side effect",
        "side effects",
        "interaction",
        "with",
        "together",
        "combine",
        "warfarin",
        "ibuprofen",
        "paracetamol",
        "acetaminophen",
        "metformin",
        "antibiotic",
    ]

    return any(m in q for m in med_markers)


def extract_keywords(query: str) -> dict:
    """
    Returns:
    {
      "mandatory": [...],   # must appear in title/content
      "optional": [...]     # bonus if appears
    }
    """
    q = _normalize_text(query)

    m = re.search(
        r"(?:the\s+)?(symptoms|signs|treatment|treat|causes|cause)\s+(?:of|for)\s+([a-z0-9\s\-]+)",
        q
    )

    if m:
        disease_phrase = m.group(2).strip()
        disease_phrase = disease_phrase.strip(" ?.!:,;\"'")
        disease_tokens = [t for t in disease_phrase.split() if len(t) >= 3][:3]
        mandatory = disease_tokens
    else:
        mandatory = []

    tokens = re.findall(r"[a-z0-9]+", q)

    stop = {
        "what", "are", "the", "is", "of", "in", "on", "for", "to", "and", "a", "an",
        "with", "without", "how", "when", "why", "can", "i", "my", "your", "me", "tell",
        "symptoms", "symptom", "signs", "sign", "cause", "causes", "treat", "treatment"
    }

    optional = [t for t in tokens if t not in stop and len(t) >= 3]
    optional = [t for t in optional if t not in mandatory]

    def uniq(lst):
        seen = set()
        out = []
        for x in lst:
            if x not in seen:
                out.append(x)
                seen.add(x)
        return out

    return {
        "mandatory": uniq(mandatory),
        "optional": uniq(optional)[:5]
    }


def keyword_match_score(doc: MedicalDocument, keywords: list[str]) -> float:
    if not keywords:
        return 0.0

    title = _normalize_text(doc.title)
    content = _normalize_text(doc.content)

    hits = 0
    strong_hits = 0

    for kw in keywords:
        if kw in title:
            hits += 1
            strong_hits += 1
        elif kw in content:
            hits += 1

    return (hits * 0.15) + (strong_hits * 0.25)


# ------------------------------------------------------------------
# AUTHORITY WEIGHTS (DETERMINISTIC)
# ------------------------------------------------------------------

AUTHORITY_WEIGHTS = {
    "CDC": 3,
    "CDC Emergency Guidelines": 3,
    "WHO": 3,
    "NIH": 3,
    "MedQuAD": 2,
    "Clinical Handbook": 2,
    "Generic": 1,
}


def _authority_score(source: Optional[str], explicit_level: Optional[int]) -> int:
    if explicit_level is not None:
        return explicit_level
    if not source:
        return 1

    s = source.strip().lower()
    if "medquad" in s:
        return AUTHORITY_WEIGHTS["MedQuAD"]
    if "cdc" in s:
        return AUTHORITY_WEIGHTS["CDC"]
    if "who" in s:
        return AUTHORITY_WEIGHTS["WHO"]
    if "nih" in s:
        return AUTHORITY_WEIGHTS["NIH"]

    return 1


# ------------------------------------------------------------------
# EMBEDDING (LOCAL / FREE) — SAFE FOR RENDER
# ------------------------------------------------------------------

from threading import Lock

_embedding_model = None
_embedding_lock = Lock()
EMBEDDING_DIM = 384


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                from sentence_transformers import SentenceTransformer
                _embedding_model = SentenceTransformer(
                    "sentence-transformers/all-MiniLM-L6-v2",
                    device="cpu"
                )
    return _embedding_model


def _generate_embedding(text: str) -> list[float]:
    try:
        model = _get_embedding_model()
        if model is None:
            raise RuntimeError("Embedding model unavailable")
        return model.encode(text, normalize_embeddings=True).tolist()
    except Exception as e:
        # IMPORTANT: fail gracefully
        from app.utils.logger import logger  # or logging.getLogger("medibot")
        logger.error(f"Embedding generation failed: {e}")
        return []


# ------------------------------------------------------------------
# CITATION BUILDER
# ------------------------------------------------------------------

def build_citation(doc: MedicalDocument) -> Dict[str, Any]:
    return {
        "document_id": doc.id,
        "title": doc.title,
        "source": doc.source,
        "source_file": doc.source_file,
        "page_number": doc.page_number,
        "chunk_index": doc.chunk_index,
        "medical_domain": doc.medical_domain,
        "authority_level": doc.authority_level,
    }


# ------------------------------------------------------------------
# INTERNAL: candidate fetch
# ------------------------------------------------------------------

def _fetch_candidates(
    *,
    db: Session,
    base_query,
    query_embedding: list[float],
    limit: int,
    mandatory_filter,
    optional_filter,
) -> list[MedicalDocument]:
    """
    Fetch candidates using:
    - vector ordering
    - lexical filtering
    - merged unique results
    """
    # Vector candidates
    vector_query = base_query
    if mandatory_filter is not None:
        vector_query = vector_query.filter(mandatory_filter)

    vector_candidates = (
        vector_query
        .order_by(MedicalDocument.embedding.cosine_distance(query_embedding))
        .limit(limit * 20)
        .all()
    )

    # Lexical candidates
    lexical_query = base_query
    if mandatory_filter is not None:
        lexical_query = lexical_query.filter(mandatory_filter)
    elif optional_filter is not None:
        lexical_query = lexical_query.filter(optional_filter)

    lexical_candidates = (
        lexical_query
        .limit(limit * 20)
        .all()
    )

    merged: dict[int, MedicalDocument] = {}
    for d in vector_candidates + lexical_candidates:
        merged[d.id] = d

    return list(merged.values())


# ------------------------------------------------------------------
# PUBLIC RAG API
# ------------------------------------------------------------------

def retrieve_context(
    *,
    query: str,
    limit: int = 3,
    medical_domain: Optional[str] = None,
    is_emergency: Optional[bool] = None,
    min_authority_level: Optional[int] = None,
    db: Optional[Session] = None,
) -> RAGResult:
    """
    Returns a RAGResult object that supports:
      - legacy list[str] indexing (context[0] gives first chunk text)
      - tuple unpacking: chunks, confidence = retrieve_context(...)
    """

    query_embedding = _generate_embedding(query)

    if settings.VECTOR_BACKEND != "pgvector":
        raise RuntimeError("Only pgvector backend supported for explainable RAG")

    if db is None:
        raise RuntimeError("DB session required for pgvector backend")

    # -----------------------------
    # Filters
    # -----------------------------
    filters = []
    strict_domain = medical_domain and not is_emergency

    if strict_domain:
        filters.append(MedicalDocument.medical_domain == medical_domain)

    if is_emergency is True:
        filters.append(MedicalDocument.is_emergency.is_(True))

    if min_authority_level is not None:
        filters.append(
            (MedicalDocument.authority_level >= min_authority_level)
            | (MedicalDocument.authority_level.is_(None))
        )

    base_query = db.query(MedicalDocument)
    if filters:
        base_query = base_query.filter(and_(*filters))

    # -----------------------------
    # Keyword extraction
    # -----------------------------
    kw = extract_keywords(query)
    mandatory_keywords = kw.get("mandatory", [])
    optional_keywords = kw.get("optional", [])

    mandatory_filter = mandatory_keyword_filter(mandatory_keywords)

    optional_filter = None
    if optional_keywords:
        optional_filter = or_(
            *[
                or_(
                    MedicalDocument.title.ilike(f"%{k}%"),
                    MedicalDocument.content.ilike(f"%{k}%"),
                )
                for k in optional_keywords
            ]
        )

    # -----------------------------
    # Step A/B: candidates (strict)
    # -----------------------------
    results = _fetch_candidates(
        db=db,
        base_query=base_query,
        query_embedding=query_embedding,
        limit=limit,
        mandatory_filter=mandatory_filter,
        optional_filter=optional_filter,
    )

    # -----------------------------
    # NEW: Fallback if mandatory filter was too strict
    # -----------------------------
    # Example: "dengue fever" => requires both dengue AND fever.
    # If docs only contain "dengue", strict mandatory filter returns empty.
    if not results and mandatory_filter is not None:
        results = _fetch_candidates(
            db=db,
            base_query=base_query,
            query_embedding=query_embedding,
            limit=limit,
            mandatory_filter=None,            # relax mandatory constraint
            optional_filter=optional_filter,  # still keep optional guidance
        )

    # -----------------------------
    # Medication multi-term fallback (OR filter)
    # Run this even if we got weak vector results, because medication queries
    # often need lexical anchoring (ibuprofen/warfarin may not co-occur in one chunk).
    # -----------------------------
    if looks_like_medication_query(query):
        med_terms_raw = mandatory_keywords if mandatory_keywords else optional_keywords
        med_terms = _clean_med_terms(med_terms_raw)

        # If we have >=2 meaningful terms, run OR lexical anchored retrieval
        if len(med_terms) >= 2:
            or_filter = any_keyword_filter(med_terms)

            med_results = _fetch_candidates(
                db=db,
                base_query=base_query,
                query_embedding=query_embedding,
                limit=limit,
                mandatory_filter=None,
                optional_filter=or_filter,
            )

            # Merge med_results with existing results (don’t lose anything)
            merged = {d.id: d for d in (results or [])}
            for d in med_results:
                merged[d.id] = d
            results = list(merged.values())    

    # -----------------------------
    # Emergency fallback (domain relaxation)
    # -----------------------------
    if not results and is_emergency and medical_domain:
        fallback_filters = [MedicalDocument.is_emergency.is_(True)]
        if min_authority_level is not None:
            fallback_filters.append(MedicalDocument.authority_level >= min_authority_level)

        results = (
            db.query(MedicalDocument)
            .filter(and_(*fallback_filters))
            .order_by(MedicalDocument.embedding.cosine_distance(query_embedding))
            .limit(limit * 20)
            .all()
        )

    # -----------------------------
    # Rerank
    # -----------------------------
    scored = []
    all_keywords_for_bonus = mandatory_keywords + optional_keywords

    for doc in results:
        if doc.embedding is None:
            continue

        sim = cosine_similarity(doc.embedding, query_embedding)
        auth = _authority_score(doc.source, doc.authority_level)

        authority_bonus = 0.03 * auth
        kw_bonus = keyword_match_score(doc, all_keywords_for_bonus)
        domain_bonus = 0.05 if (medical_domain and doc.medical_domain == medical_domain) else 0.0

        title_norm = _normalize_text(doc.title)
        mandatory_title_boost = 0.0
        if mandatory_keywords and all(k in title_norm for k in mandatory_keywords):
            mandatory_title_boost = 0.35

        final_score = sim + kw_bonus + authority_bonus + domain_bonus + mandatory_title_boost
        scored.append((final_score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    final_docs = [doc for _, doc in scored[:limit]]

    chunks: list[dict] = []
    for idx, doc in enumerate(final_docs, start=1):
        chunks.append(
            {
                "chunk_number": idx,
                "chunk_id": doc.id,
                "content": doc.content,
                "citation": build_citation(doc),
            }
        )

    if not scored:
        return RAGResult([], 0.0)

    best_score = scored[0][0]
    coverage = len(chunks) / max(limit, 1)
    confidence_score = max(0.0, min(1.0, (best_score * 0.7) + (coverage * 0.3)))

    return RAGResult(chunks, confidence_score)



















