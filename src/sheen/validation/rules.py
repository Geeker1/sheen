from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel


class DateRules(BaseModel):
    earliest_plausible: date


class QuantityRules(BaseModel):
    max_plausible_bbl: float


class CoordinateRules(BaseModel):
    projected_candidate_srids: list[int]
    offshore_max_distance_km: float
    offshore_max_latitude: float
    offshore_lon_range: tuple[float, float]
    reused_min_incidents: int


class LgaMatchRules(BaseModel):
    min_similarity: float
    tie_break_km: float


class StateMatchRules(BaseModel):
    border_tolerance_m: float


class DuplicateRules(BaseModel):
    radius_m: float
    window_days: int


class Ruleset(BaseModel):
    version: str
    dates: DateRules
    quantity: QuantityRules
    coordinates: CoordinateRules
    lga_match: LgaMatchRules
    state_match: StateMatchRules
    duplicates: DuplicateRules


@lru_cache
def load(path: Path) -> Ruleset:
    return Ruleset.model_validate(yaml.safe_load(path.read_text()))
