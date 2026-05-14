from sqlalchemy import Boolean, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.enums import ReportingCategoryType, TaxInputOutputType
from app.db.models.mixins import PrimaryKeyMixin, TimestampMixin


class ReportingCategory(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reporting_categories"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_reporting_category_code"),)

    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    category_type: Mapped[ReportingCategoryType] = mapped_column(
        Enum(ReportingCategoryType),
        nullable=False,
    )


class TaxCode(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tax_codes"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_tax_code"),)

    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    rate: Mapped[float] = mapped_column(Numeric(9, 4), nullable=False)
    is_gst_applicable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bas_label: Mapped[str | None] = mapped_column(String(32))
    input_output_type: Mapped[TaxInputOutputType] = mapped_column(
        Enum(TaxInputOutputType),
        nullable=False,
    )
