from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import ScanStage, ScanStatus


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(RegisterRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ScanCreateRequest(BaseModel):
    repo_url: str = Field(min_length=1, max_length=200)

    @field_validator("repo_url")
    @classmethod
    def validate_raw_url(cls, value):
        from app.services.repository import validate_github_url
        validate_github_url(value)
        return value


class ScanCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    scan_id: int
    status: ScanStatus
    stage: ScanStage
    estimated_min_seconds: int | None
    estimated_max_seconds: int | None

class ScanHistoryResponse(BaseModel):
    id: int
    repo_url: str | None
    status: ScanStatus
    stage: ScanStage
    estimated_min_seconds: int | None
    estimated_max_seconds: int | None
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
    priority: str = "p4"
    priority_score: int = 0
    priority_reasons: list[str] = Field(default_factory=list)


class FileHotspot(BaseModel):
    file_path: str
    finding_count: int
    severity_counts: dict[str, int]
    weight: float


class ScanComparison(BaseModel):
    available: bool
    reason: str | None = None
    baseline_scan_id: int | None = None
    baseline_commit: str | None = None
    current_commit: str | None = None
    identity_mode: str | None = None
    warnings: list[str] = Field(default_factory=list)
    score_delta: int | None = None
    total_delta: int | None = None
    severity_delta: dict[str, int] = Field(default_factory=dict)
    new_issue_ids: list[int] = Field(default_factory=list)
    unchanged_issue_ids: list[int] = Field(default_factory=list)
    resolved_issues: list[IssueResponse] = Field(default_factory=list)
    new_count: int = 0
    resolved_count: int = 0
    unchanged_count: int = 0


class ScanResponse(BaseModel):
    id: int
    repo_url: str | None
    status: ScanStatus
    stage: ScanStage
    estimated_min_seconds: int | None
    estimated_max_seconds: int | None
    score: int | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    issues: list[IssueResponse]
    source_commit: str | None = None
    priority_version: str = "1"
    top_issue_ids: list[int] = Field(default_factory=list)
    hotspots: list[FileHotspot] = Field(default_factory=list)
