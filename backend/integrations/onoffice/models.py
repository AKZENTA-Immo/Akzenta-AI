from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

class OnOfficeStatus(BaseModel):
    enabled: bool
    mode: str
    configured: bool
    reachable: bool = False
    authenticated: bool = False
    api_url: str
    permissions_checked: bool = False
    last_check: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None

class OnOfficeSearchRequest(BaseModel):
    filters: dict[str, str | int | float] = Field(min_length=1, max_length=5)
    limit: int = Field(default=10, ge=1, le=25)
    offset: int = Field(default=0, ge=0, le=10000)

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, value):
        if any(not str(item).strip() or len(str(item)) > 200 for item in value.values()):
            raise ValueError("Suchwerte dürfen nicht leer oder überlang sein.")
        return value

class OnOfficeRecord(BaseModel):
    id: int
    type: Literal["address", "estate"]
    data: dict[str, Any]
    unmapped_fields: list[str] = Field(default_factory=list)

class OnOfficeSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    records: list[OnOfficeRecord]
