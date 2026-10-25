"""
Pydantic data models and serialization helpers for 4D BIM schedule crashing,
milestone payment tracking, and S-curve progress logging.
"""

from pathlib import Path
from typing import Dict, List, Literal, Optional, Union
from debim.compat import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class ProgressLogEntry(BaseModel):
    date: str
    percent: float
    notes: Optional[str] = None

    @field_validator("percent")
    @classmethod
    def validate_percent(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError(f"percent must be between 0.0 and 100.0, got {v}")
        return v


class Milestone(BaseModel):
    id: str
    name: str
    payment_percent: Optional[float] = None
    payment_amount: Optional[float] = None
    required_activities: List[str] = Field(default_factory=list)

    @field_validator("payment_percent")
    @classmethod
    def validate_payment_percent(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError(f"payment_percent must be between 0.0 and 100.0, got {v}")
        return v


class CrashingActivity(BaseModel):
    # Plan / Crashing fields
    id: str
    name: str
    element_ids: List[str] = Field(default_factory=list)
    predecessors: List[str] = Field(default_factory=list)
    normal_duration: int
    crash_duration: int
    normal_cost: float = 0.0
    crash_cost: float = 0.0
    cost_weight: Optional[float] = None

    # As-Built / Actual Progress fields
    status: Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED"] = "NOT_STARTED"
    progress_percent: float = 0.0
    actual_start: Optional[str] = None
    actual_finish: Optional[str] = None
    progress_log: List[ProgressLogEntry] = Field(default_factory=list)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_activity_bounds(self) -> "CrashingActivity":
        if self.normal_duration < 0:
            raise ValueError("normal_duration must be non-negative")
        if self.crash_duration < 0:
            raise ValueError("crash_duration must be non-negative")
        if self.crash_duration > self.normal_duration:
            raise ValueError(
                f"crash_duration ({self.crash_duration}) cannot exceed normal_duration ({self.normal_duration})"
            )
        if self.normal_cost < 0.0:
            raise ValueError("normal_cost must be non-negative")
        if self.crash_cost < 0.0:
            raise ValueError("crash_cost must be non-negative")
        if not (0.0 <= self.progress_percent <= 100.0):
            raise ValueError("progress_percent must be between 0.0 and 100.0")
        if self.cost_weight is None:
            self.cost_weight = self.normal_cost
        elif self.cost_weight < 0.0:
            raise ValueError("cost_weight must be non-negative")
        return self


class CrashingManifest(BaseModel):
    project_id: str
    as_of_date: Optional[str] = None
    overhead_per_day: float = 0.0
    max_budget: Optional[float] = None
    milestones: List[Milestone] = Field(default_factory=list)
    activities: List[CrashingActivity]


class MilestoneResult(BaseModel):
    id: str
    name: str
    payment_percent: float
    planned_completion_day: int
    actual_completion_day: Optional[int] = None
    is_completed: bool = False
    billing_status: Literal["PENDING", "READY_FOR_BILLING", "PAID"] = "PENDING"


class SCurveData(BaseModel):
    dates: List[str] = Field(default_factory=list)
    planned_early_percent: List[float] = Field(default_factory=list)
    planned_late_percent: List[float] = Field(default_factory=list)
    actual_percent: List[float] = Field(default_factory=list)


class ActivityScheduleResult(BaseModel):
    id: str
    start_day: int
    finish_day: int
    duration: int
    crashed_days: int
    added_cost: float
    is_critical: bool
    progress_percent: float = 0.0
    status: str = "NOT_STARTED"


class ScheduleResult(BaseModel):
    project_id: str
    status: str
    total_duration: int
    total_direct_cost: float
    total_indirect_cost: float
    total_cost: float
    overall_progress_percent: float = 0.0
    critical_path: List[str]
    activities: Dict[str, ActivityScheduleResult]
    milestones: List[MilestoneResult] = Field(default_factory=list)
    s_curve: SCurveData = Field(default_factory=SCurveData)


def load_schedule_yaml(path: Union[Path, str]) -> CrashingManifest:
    """Load and parse a schedule.yaml file into a CrashingManifest instance."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Schedule file not found: {p}")
    from debim.loader import parse_debim

    with open(p, "r", encoding="utf-8") as f:
        data = parse_debim(f) or {}
    return CrashingManifest.model_validate(data)


def dump_schedule_json(result: ScheduleResult, path: Union[Path, str]) -> Path:
    """Serialize a ScheduleResult to JSON and write to disk."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    json_str = result.model_dump_json(indent=2)
    p.write_text(json_str, encoding="utf-8")
    return p
