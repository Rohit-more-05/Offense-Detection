import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

class ScanHistory(Base):
    """
    SQLAlchemy ORM model for the `scan_history` table tracking multimodal model scans.
    """
    __tablename__ = "scan_history"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    
    image_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_text: Mapped[str] = mapped_column(String(2048), nullable=True)
    harmful_probability: Mapped[float] = mapped_column(Float, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return f"<ScanHistory id={self.id!r} prob={self.harmful_probability:.4f}>"
