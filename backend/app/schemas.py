from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

SectorCode = Literal["soviet", "american", "british", "french"]
DatasetStatus = Literal["ready", "missing"]


class PointQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
    lng: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class SectorInfo(BaseModel):
    id: int
    code: SectorCode
    name: str
    source_name: str
    source_url: str


class SectorProperties(SectorInfo):
    sector: SectorCode


class GeometryOutput(BaseModel):
    type: Literal["MultiPolygon"] = "MultiPolygon"
    coordinates: list[list[list[list[float]]]]


class SectorFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: int
    properties: SectorProperties
    geometry: GeometryOutput


class SectorCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[SectorFeature]
    dataset_status: DatasetStatus


class Identification(BaseModel):
    dataset_status: DatasetStatus
    sector: SectorInfo | None


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
    dataset_status: DatasetStatus
