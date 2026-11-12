import json

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OccupationSector
from app.schemas import SectorInfo

SECTOR_NAMES = {"soviet": "Soviet", "american": "American", "british": "British", "french": "French"}


def dataset_status(session: Session) -> str:
    codes = set(session.scalars(select(OccupationSector.code)))
    if not codes:
        return "missing"
    if codes != set(SECTOR_NAMES):
        raise HTTPException(503, detail="Historical dataset is incomplete; import all four sectors.")
    return "ready"


def info(sector: OccupationSector) -> SectorInfo:
    return SectorInfo(id=sector.id, code=sector.code, name=sector.name,
                      source_name=sector.source_name, source_url=sector.source_url)


def collection(session: Session):
    # One statement gives features and completeness from the same database snapshot.
    rows = session.execute(select(OccupationSector, func.ST_AsGeoJSON(OccupationSector.geometry)).order_by(OccupationSector.code)).all()
    if rows and {row[0].code for row in rows} != set(SECTOR_NAMES):
        raise HTTPException(503, detail="Historical dataset is incomplete; import all four sectors.")
    return {
        "type": "FeatureCollection", "dataset_status": "ready" if rows else "missing",
        "features": [
            {"type": "Feature", "id": sector.id, "properties": {**info(sector).model_dump(), "sector": sector.code},
             "geometry": json.loads(geometry)} for sector, geometry in rows
        ],
    }


def identify(session: Session, lat: float, lng: float):
    # ST_Covers includes the boundary. Shared edges resolve by stable code order.
    point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
    sector = session.scalar(select(OccupationSector).where(
        func.ST_Covers(OccupationSector.geometry, point)
    ).order_by(OccupationSector.code).limit(1))
    return info(sector) if sector else None
