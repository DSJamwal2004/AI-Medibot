from sqlalchemy import Column, Integer, String, Text, SmallInteger, Boolean
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class MedicalDocument(Base):
    __tablename__ = "medical_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    source = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    # Vector
    embedding = Column(Vector(384), nullable=True)

    # Metadata (existing)
    medical_domain = Column(String, nullable=True)
    content_type = Column(String, nullable=True)
    authority_level = Column(SmallInteger, nullable=True)
    is_emergency = Column(Boolean, nullable=True)
    published_by = Column(String, nullable=True)

    # 🔹 PDF explainability metadata (ADD THESE)
    source_file = Column(String, nullable=True)
    page_number = Column(Integer, nullable=True)
    chunk_index = Column(Integer, nullable=True)



