import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.privacy import suppress_identification_access_logs
from app.repository import collection, dataset_status, identify
from app.schemas import Health, Identification, PointQuery, SectorCollection

suppress_identification_access_logs()

app = FastAPI(title="Berliner Map API", version="0.2.0")
Db = Annotated[Session, Depends(get_db)]
logger = logging.getLogger(__name__)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logger.error("Database operation failed for %s: %s", request.url.path, type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Database unavailable or migrations required."})


@app.get("/api/v1/health", response_model=Health)
def health(db: Db):
    db.execute(text("SELECT PostGIS_Version()"))
    return {"status": "ok", "database": "ok", "dataset_status": dataset_status(db)}


@app.get("/api/v1/sectors", response_model=SectorCollection)
def sectors(db: Db):
    return collection(db)


@app.get("/api/v1/sectors/identify", response_model=Identification)
def identify_sector(point: Annotated[PointQuery, Query()], db: Db):
    status = dataset_status(db)
    return {"dataset_status": status, "sector": identify(db, point.lat, point.lng) if status == "ready" else None}
