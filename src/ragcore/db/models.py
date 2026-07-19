"""ORM models — MUST mirror db_bootstrap.sql (§1.2 documents, §1.3 chunks).

Schema is owned by db_bootstrap.sql + Alembic; these models are the Python view of it.
Any schema change goes through an Alembic migration, not by editing the live DB.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ragcore.config import settings


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    page_count: Mapped[int | None] = mapped_column(Integer)
    markdown_path: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="validating")
    error_message: Mapped[str | None] = mapped_column(Text)

    summary_text: Mapped[str | None] = mapped_column(Text)
    summary_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    summary_model: Mapped[str | None] = mapped_column(Text)
    summary_generated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))

    content_hash: Mapped[str | None] = mapped_column(Text)   # banked for future dedup
    company: Mapped[str | None] = mapped_column(Text)        # enrichment (§2.1b)
    fiscal_period: Mapped[str | None] = mapped_column(Text)

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('validating','processing','ready','failed')",
            name="documents_status_chk",
        ),
        CheckConstraint(
            "summary_status IN ('pending','generating','completed','failed')",
            name="documents_summary_status_chk",
        ),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.doc_id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)   # RAW text (§3.4)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embed_dim))
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)

    # generated column — Postgres maintains it from raw `content`; read-only here.
    content_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        server_default=text("to_tsvector('english', content)"),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("chunks_embedding_hnsw", "embedding",
              postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("chunks_content_tsv_gin", "content_tsv", postgresql_using="gin"),
        Index("chunks_doc_id_idx", "doc_id"),
        Index("chunks_doc_order_idx", "doc_id", "chunk_index"),
    )
