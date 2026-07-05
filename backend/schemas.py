from pydantic import BaseModel, Field
from typing import List, Optional


class Vulnerability(BaseModel):
    type: str = Field(description="Vulnerability name, e.g. SQL Injection")
    severity: str = Field(description="critical, high, medium, or low")
    line: str = Field(description="The exact vulnerable code statement")
    fix: str = Field(description="Specific, actionable remediation instruction")


class ReviewOutput(BaseModel):
    score: int = Field(description="Code quality score from 0 to 10")
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    complexity: str = Field(description="low, medium, or high")
    summary: str


class SecurityOutput(BaseModel):
    is_safe: bool
    risk_score: int
    vulnerabilities: List[Vulnerability] = Field(default_factory=list)


class AutoFixOutput(BaseModel):
    fixed_code: Optional[str] = None
    changes_made: List[str] = Field(default_factory=list)
    explanation: str = ""


class DocumentationOutput(BaseModel):
    summary: str