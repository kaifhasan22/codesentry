from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.models import ScanStatus


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(RegisterRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ScanCreateRequest(BaseModel):
    repo_url: HttpUrl


class ScanCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    scan_id: int
    status: ScanStatus

class ScanHistoryResponse(BaseModel):
    id: int
    repo_url: str | None
    status: ScanStatus
    score: int | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    issue_count: int


class ScanHistoryPage(BaseModel):
    items: list[ScanHistoryResponse]
    total: int
    limit: int | None
    offset: int


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    severity: str
    title: str
    message: str
    file_path: str
    line: int | None
    snippet: str | None
    ai_explanation: str | None
    fix_suggestion: str | None


class ScanResponse(BaseModel):
    id: int
    repo_url: str | None
    status: ScanStatus
    score: int | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    issues: list[IssueResponse]
