"""Public API contracts, including rejection of NaN and infinity."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["NORMAL", "WARNING", "CRITICAL"]


class Telemetry(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid", str_strip_whitespace=True, strict=True)
    robot_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    timestamp: float = Field(ge=0)
    x: float
    y: float
    speed: float = Field(ge=0)
    battery: float = Field(ge=0, le=100)
    motor_temp: float
    vibration: float = Field(ge=0)
    motor_current: float = Field(ge=0)
    obstacle_distance: float = Field(ge=0)


class Prediction(BaseModel):
    robot_id: str
    predicted_status: Status
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    model_version: str
    inference_ms: float = Field(ge=0, allow_inf_nan=False)
