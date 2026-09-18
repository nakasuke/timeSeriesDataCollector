from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class RangeHint(BaseModel):
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_order(self):
        if self.start_time > self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class AvailableRangeRequest(BaseModel):
    signal_ids: list[str] = Field(min_length=1, max_length=1000)
    range_hint: RangeHint | None = None
    allow_partial: bool = False


class DataQueryRequest(BaseModel):
    signal_ids: list[str] = Field(min_length=1, max_length=100)
    start_time: datetime
    end_time: datetime
    max_points_per_signal: int = Field(default=2000, ge=10, le=10000)

    @model_validator(mode="after")
    def validate_order(self):
        if self.start_time > self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    postgres: Literal["ok"] = "ok"
    gremlin: Literal["ok"] = "ok"

