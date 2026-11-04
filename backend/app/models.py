import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Master catalog tables -------------------------------------------------

class MaterialGrade(SQLModel, table=True):
    __tablename__ = "material_grades"

    grade_id: str = Field(primary_key=True)  # e.g. 'ASTM A106 GRADE B'
    category: str  # 'CARBON STEEL', 'STAINLESS', 'NICKEL ALLOY', ...
    is_exotic: bool = False


class PipeSchedule(SQLModel, table=True):
    __tablename__ = "pipe_schedules"

    schedule_id: Optional[int] = Field(default=None, primary_key=True)
    nominal_pipe_size: str  # e.g. '4"', '1/2"'
    schedule_name: str  # e.g. 'SCH 40', 'STD', 'XS'
    outer_diameter_in: float
    wall_thickness_in: float


# --- Operational tables ------------------------------------------------------

class RFQSubmission(SQLModel, table=True):
    __tablename__ = "rfq_submissions"

    rfq_id: str = Field(default_factory=_uuid, primary_key=True)
    customer_name: Optional[str] = None
    raw_text: str
    source_filename: Optional[str] = None
    # PENDING -> AUTO_APPROVED | HUMAN_REVIEW -> QUOTED
    status: str = "PENDING"
    extractor_used: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class RFQLineItem(SQLModel, table=True):
    __tablename__ = "rfq_line_items"

    item_id: str = Field(default_factory=_uuid, primary_key=True)
    rfq_id: str = Field(foreign_key="rfq_submissions.rfq_id")
    raw_line_text: str

    product_category: Optional[str] = None
    extracted_material: Optional[str] = None
    extracted_size: Optional[str] = None
    extracted_schedule: Optional[str] = None
    quantity: Optional[int] = None
    unit_of_measure: str = "EA"

    confidence_score: Optional[float] = None
    requires_human_review: bool = False
    validation_notes: list = Field(default_factory=list, sa_column=Column(JSON))

    # Set when a sales rep reviews / overrides the item in the UI.
    reviewed: bool = False
    unit_price: Optional[float] = None
