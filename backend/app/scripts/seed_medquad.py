from pathlib import Path
import xml.etree.ElementTree as ET

from sentence_transformers import SentenceTransformer

from app.db.session import SessionLocal
from app.models.medical_document import MedicalDocument

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
MEDQUAD_ROOT = Path(__file__).resolve().parents[3] / "datasets" / "medquad"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384-dim

model = SentenceTransformer(EMBEDDING_MODEL)


# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def generate_embedding(text: str):
    return model.encode(text, normalize_embeddings=True).tolist()


def parse_medquad_xml(file_path: Path):
    """
    Parse a MedQuAD XML file and extract question, answer, source.
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        question = root.findtext(".//Question")
        answer = root.findtext(".//Answer")
        source = root.findtext(".//Source")

        if not question or not answer:
            return None

        return question.strip(), answer.strip(), source or "MedQuAD"

    except ET.ParseError:
        return None


# -------------------------------------------------
# MAIN SEEDER
# -------------------------------------------------
def seed_medquad():
    db = SessionLocal()
    inserted = 0

    for source_dir in MEDQUAD_ROOT.iterdir():
        if not source_dir.is_dir():
            continue

        source_name = source_dir.name.replace("_QA", "")

        for xml_file in source_dir.glob("*.xml"):
            parsed = parse_medquad_xml(xml_file)
            if not parsed:
                continue

            question, answer, xml_source = parsed
            content = f"Question: {question}\nAnswer: {answer}"

            embedding = generate_embedding(content)

            doc = MedicalDocument(
                title=question[:255],
                source=f"MedQuAD - {source_name}",
                content=content,
                embedding=embedding,
            )

            db.add(doc)
            inserted += 1

            if inserted % 200 == 0:
                db.commit()
                print(f"Inserted {inserted} documents...")

    db.commit()
    db.close()

    print(f"✅ MedQuAD seeding completed. Total inserted: {inserted}")


if __name__ == "__main__":
    seed_medquad()

