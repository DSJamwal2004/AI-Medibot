from pathlib import Path
from typing import List, Optional, Tuple

from pypdf import PdfReader
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.session import SessionLocal
from app.models.medical_document import MedicalDocument
from app.services.rag_service import _generate_embedding


# ------------------------------------------------------------------
# Path resolution (project-root safe)
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[3]
PDF_ROOT = BASE_DIR / "datasets/pdf"


# ------------------------------------------------------------------
# Chunking configuration
# ------------------------------------------------------------------

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


# ------------------------------------------------------------------
# Chunking utility
# ------------------------------------------------------------------

def chunk_text(text: str) -> List[str]:
    words = (text or "").split()
    chunks = []

    start = 0
    while start < len(words):
        end = start + CHUNK_SIZE
        chunk = words[start:end]
        if chunk:
            chunks.append(" ".join(chunk))
        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


# ------------------------------------------------------------------
# Metadata helpers
# ------------------------------------------------------------------

def infer_domain_from_path(pdf_path: Path) -> str:
    """
    Domain is inferred from folder name under datasets/pdf/
    Example: datasets/pdf/covid/file.pdf -> "covid"
    """
    try:
        rel = pdf_path.relative_to(PDF_ROOT)
        if len(rel.parts) >= 2:
            return rel.parts[0].lower()
    except Exception:
        pass
    return "general"


def infer_publisher_and_authority(pdf_path: Path, domain: str) -> Tuple[str, int, str]:
    """
    Returns: (published_by, authority_level, source_label)
    authority_level: 1..3 (3 = highest)
    """
    name = pdf_path.name.lower()

    # CDC
    if "cdc" in name:
        return ("CDC", 3, "CDC PDF")

    # WHO
    if "who" in name:
        return ("WHO", 3, "WHO PDF")

    # MoHFW (India)
    if "mohfw" in name or "ministry" in name:
        return ("MoHFW", 3, "MoHFW PDF")

    # COVID docs you added (MoHFW but filenames may not contain mohfw)
    if domain in {"covid", "infectious_disease"}:
        return ("MoHFW", 3, "MoHFW COVID Guidance")

    # Default
    return ("Generic", 2, "Uploaded PDF")


def infer_title(pdf_path: Path) -> str:
    """
    Use a readable title derived from filename.
    """
    stem = pdf_path.stem.replace("_", " ").replace("-", " ").strip()
    # Avoid extremely long titles
    if len(stem) > 120:
        stem = stem[:120].rstrip()
    return stem or pdf_path.name


def detect_emergency_chunk(text: str) -> bool:
    """
    Lightweight chunk-level emergency hint.
    This does NOT affect your medical_safety emergency detection in chat,
    it's only for document metadata.
    """
    lowered = (text or "").lower()

    emergency_markers = [
        "call 9-1-1",
        "call 911",
        "call emergency",
        "seek immediate",
        "seek urgent",
        "emergency",
        "go to the emergency",
        "go to nearest hospital",
    ]

    return any(m in lowered for m in emergency_markers)


# ------------------------------------------------------------------
# Duplicate check
# ------------------------------------------------------------------

def chunk_exists(
    db: Session,
    *,
    source_file: str,
    page_number: int,
    chunk_index: int,
    medical_domain: str,
) -> bool:
    """
    Prevent duplicates when re-running ingestion.
    """
    existing = (
        db.query(MedicalDocument.id)
        .filter(
            and_(
                MedicalDocument.source_file == source_file,
                MedicalDocument.page_number == page_number,
                MedicalDocument.chunk_index == chunk_index,
                MedicalDocument.medical_domain == medical_domain,
            )
        )
        .first()
    )
    return existing is not None


# ------------------------------------------------------------------
# Ingestion
# ------------------------------------------------------------------

def iter_pdfs(root: Path) -> List[Path]:
    if not root.exists():
        raise FileNotFoundError(f"PDF root folder not found: {root}")

    return sorted([p for p in root.rglob("*.pdf") if p.is_file()])


def ingest_single_pdf(db: Session, pdf_path: Path) -> int:
    domain = infer_domain_from_path(pdf_path)
    published_by, authority_level, source_label = infer_publisher_and_authority(pdf_path, domain)
    title = infer_title(pdf_path)

    reader = PdfReader(str(pdf_path))

    inserted = 0
    skipped = 0

    for page_idx, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if not text or len(text.strip()) < 50:
            continue

        chunks = chunk_text(text)

        for chunk_idx, chunk in enumerate(chunks):
            # Skip duplicates
            if chunk_exists(
                db,
                source_file=pdf_path.name,
                page_number=page_idx,
                chunk_index=chunk_idx,
                medical_domain=domain,
            ):
                skipped += 1
                continue

            is_emergency = detect_emergency_chunk(chunk)
            content_type = "emergency" if is_emergency else "educational"

            doc = MedicalDocument(
                title=title,
                source=source_label,
                content=chunk,
                medical_domain=domain,
                content_type=content_type,
                authority_level=authority_level,
                is_emergency=is_emergency,
                published_by=published_by,
                source_file=pdf_path.name,
                page_number=page_idx,
                chunk_index=chunk_idx,
            )

            # Local embedding (384 dim)
            doc.embedding = _generate_embedding(chunk)

            db.add(doc)
            inserted += 1

    print(f"📄 {pdf_path.relative_to(BASE_DIR)} -> inserted={inserted}, skipped={skipped}")
    return inserted


def ingest_all_pdfs() -> None:
    pdfs = iter_pdfs(PDF_ROOT)
    if not pdfs:
        print(f"⚠️ No PDFs found under: {PDF_ROOT}")
        return

    db: Session = SessionLocal()
    total_inserted = 0

    try:
        for pdf_path in pdfs:
            total_inserted += ingest_single_pdf(db, pdf_path)

        db.commit()
        print(f"\n✅ PDF ingestion completed. Total new chunks inserted: {total_inserted}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    ingest_all_pdfs()



