from app.db.session import SessionLocal
from app.services.rag_service import retrieve_context


def test_rag_returns_medical_context():
    db = SessionLocal()
    try:
        context = retrieve_context(
            query="chest pain",
            db=db,
        )
        assert len(context) > 0
        assert "CDC" in context[0]
    finally:
        db.close()
