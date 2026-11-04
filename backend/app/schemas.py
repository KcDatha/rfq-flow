from typing import List, Optional

from pydantic import BaseModel, Field


class ExtractedLineItem(BaseModel):
    raw_text: str = Field(description="Original line text from customer RFQ")
    product_category: str = Field(
        description="e.g. Pipe, Valve, Fitting, Flange, Stud Bolt"
    )
    material_grade: str = Field(
        description="Extracted steel alloy or grade, e.g., ASTM A106 Gr B, Monel 400"
    )
    nominal_size: str = Field(description='Size designation, e.g., 4", 2-1/2"')
    schedule_or_rating: Optional[str] = Field(
        default=None, description="e.g. SCH 40, 150#, 3000#"
    )
    quantity: int = Field(description="Quantity requested")
    unit_of_measure: str = Field(default="EA", description="EA, FT, LGT")


class RFQExtractionResult(BaseModel):
    customer_name: Optional[str] = None
    po_or_rfq_number: Optional[str] = None
    line_items: List[ExtractedLineItem]
