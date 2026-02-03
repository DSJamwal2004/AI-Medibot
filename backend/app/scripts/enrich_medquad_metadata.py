from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.medical_document import MedicalDocument
from app.services.symptom_router import infer_medical_domain


# ------------------------------------------------------------------
# Authority inference (deterministic)
# ------------------------------------------------------------------

def infer_authority(source: str) -> int:
    source = source.lower()

    if any(k in source for k in ["cdc", "nih", "medline", "nlm"]):
        return 3
    if any(k in source for k in ["hospital", "clinic", "handbook"]):
        return 2
    return 1


def infer_content_type(content: str) -> str:
    text = content.lower()
    if any(k in text for k in ["seek immediate", "emergency", "call 911"]):
        return "emergency"
    return "educational"


# ------------------------------------------------------------------
# Main enrichment job
# ------------------------------------------------------------------

def run():
    db: Session = SessionLocal()

    try:
        documents = db.query(MedicalDocument).all()
        updated = 0

        for doc in documents:
            # Re-enrich if domain is missing OR looks wrong/unknown
            bad_domains = {None, "", "unknown", "other"}
            re_enrich_general = True  # <-- ADD THIS

            needs_domain_fix = (doc.medical_domain in bad_domains) or (re_enrich_general and doc.medical_domain == "general")
            needs_authority_fix = (doc.authority_level is None)

            # If you want to ALWAYS recompute, just set both True
            if not (needs_domain_fix or needs_authority_fix):
                continue

            text_for_domain = f"""
            SOURCE: {doc.source or ""}
            TITLE: {doc.title or ""}
            CONTENT: {doc.content or ""}
            """.strip()

            domain, _ = infer_medical_domain(text_for_domain)

            authority = infer_authority(doc.source)
            content_type = infer_content_type(doc.content)

            doc.medical_domain = domain
            doc.authority_level = authority
            doc.content_type = content_type
            doc.is_emergency = content_type == "emergency"
            doc.published_by = doc.source

            updated += 1

        db.commit()
        print(f"✅ Enriched {updated} medical documents")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run()
