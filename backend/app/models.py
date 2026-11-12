from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import CheckConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OccupationSector(Base):
    __tablename__ = "occupation_sectors"
    __table_args__ = (
        CheckConstraint("code IN ('soviet', 'american', 'british', 'french')", name="ck_sector_code"),
        CheckConstraint("NOT ST_IsEmpty(geometry) AND ST_IsValid(geometry)", name="ck_sector_geometry"),
        CheckConstraint("length(trim(source_name)) > 0 AND length(trim(source_url)) > 0", name="ck_sector_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    geometry: Mapped[WKBElement] = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=True), nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
