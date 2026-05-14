from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import DocumentLinkEntityType
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class Document(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str | None] = mapped_column(String(255))
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class DocumentLink(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_links"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[DocumentLinkEntityType] = mapped_column(Enum(DocumentLinkEntityType), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    linked_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
