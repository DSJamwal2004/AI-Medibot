from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from app.db.session import SessionLocal
from app.models.medical_document import MedicalDocument


# Load local embedding model once
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def generate_embedding_local(text: str) -> list[float]:
    """
    Generate a 384-dim embedding using a free local model.
    """
    return embedding_model.encode(text).tolist()


def seed_medical_documents():
    db: Session = SessionLocal()

    documents = [
        {
            "title": "Chest Pain Emergency",
            "source": "CDC Emergency Guidelines",
            "content": (
                "Chest pain may indicate a life-threatening condition such as a heart attack. "
                "If chest pain is severe, persistent, or accompanied by shortness of breath, "
                "sweating, dizziness, or nausea, seek emergency medical care immediately."
            ),
        },
        {
            "title": "General Headache",
            "source": "Clinical Handbook",
            "content": (
                "Most headaches are not dangerous and may be caused by stress, dehydration, "
                "or lack of sleep. Persistent or severe headaches should be evaluated by a doctor."
            ),
        },
    ]

    for doc in documents:
        embedding = generate_embedding_local(doc["content"])

        db.add(
            MedicalDocument(
                title=doc["title"],
                source=doc["source"],
                content=doc["content"],
                embedding=embedding,
            )
        )

    db.commit()
    db.close()


if __name__ == "__main__":
    seed_medical_documents()



