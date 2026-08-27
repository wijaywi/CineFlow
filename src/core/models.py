"""
Core Data Models for CineFlow AI

This module defines the deterministic data structures for assets, versions,
and editing decisions. It utilizes Pydantic to ensure strict schema validation,
reproducibility, and immutability for critical assets.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from enum import Enum
import hashlib

class LicenseStatus(str, Enum):
    VERIFIED = "VERIFIED"
    DECLARED = "DECLARED"
    UNVERIFIED = "UNVERIFIED"
    POTENTIAL_COPYRIGHT_MATCH = "POTENTIAL_COPYRIGHT_MATCH"
    UNLICENSED = "UNLICENSED"
    CHECK_FAILED = "CHECK_FAILED"
    UNKNOWN = "UNKNOWN"

class RenderPermission(str, Enum):
    ALLOWED = "ALLOWED"

class AssetItem(BaseModel):
    asset_id: str
    source_uri: str
    asset_type: str = Field(description="Type of media, e.g., 'A-Roll', 'B-Roll', 'Audio'")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Rights & Provenance Layer
    owner: str
    video_license_status: LicenseStatus = LicenseStatus.UNKNOWN
    audio_license_status: LicenseStatus = LicenseStatus.UNKNOWN
    render_permission: RenderPermission = RenderPermission.ALLOWED
    commercial_use: bool = False
    derivative_allowed: bool = False
    license_warnings: List[str] = Field(default_factory=list)
    
    # Extracted Intelligence (Word-level timestamps, scenes, etc.)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        frozen = True  # Enforces immutability

class EditAction(str, Enum):
    KEEP = "KEEP"
    CUT = "CUT"
    INSERT = "INSERT"
    REMOVE = "REMOVE"

class EditDecision(BaseModel):
    clip_id: str
    action: EditAction
    start_time: float = Field(ge=0.0, description="Start timecode in precise seconds (e.g., 1.023)")
    end_time: float = Field(ge=0.0, description="End timecode in precise seconds (e.g., 5.800)")
    reasoning: str = Field(description="Agent's rationale for this decision")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Agent's confidence score (0.0 to 1.0)")
    
    @model_validator(mode='after')
    def check_times(self):
        if self.end_time <= self.start_time:
            raise ValueError(f"end_time {self.end_time} must be > start_time {self.start_time}")
        return self

class BRollInsert(BaseModel):
    clip_id: str
    insert_at_timeline: float = Field(ge=0.0, description="Insertion point on the global timeline")
    duration: float = Field(gt=0.0)
    reasoning: str

class AudioInsert(BaseModel):
    asset_id: str
    insert_at_timeline: float = Field(ge=0.0, description="Insertion point on the global timeline")
    duration: float = Field(gt=0.0)
    reasoning: str

class TimelineManifest(BaseModel):
    project_id: str
    version: int
    context: str = Field(default="")
    v1_audio_video: List[EditDecision] = Field(default_factory=list)
    v2_video_only: List[BRollInsert] = Field(default_factory=list)
    a1_audio_only: List[AudioInsert] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QualityScore(BaseModel):
    story: float = Field(default=0.0, ge=0.0, le=100.0)
    visual: float = Field(default=0.0, ge=0.0, le=100.0)
    audio: float = Field(default=0.0, ge=0.0, le=100.0)
    compliance: float = Field(default=0.0, ge=0.0, le=100.0)
    factuality: float = Field(default=0.0, ge=0.0, le=100.0)
    technical: float = Field(default=0.0, ge=0.0, le=100.0)
    
    @property
    def aggregate(self) -> float:
        return (self.story + self.visual + self.audio + self.compliance + self.factuality + self.technical) / 6.0

class ProjectState(BaseModel):
    project_id: str
    status: str = "PLANNED"
    budget_limit: float = Field(default=10.0, ge=0.0)
    current_cost: float = Field(default=0.0, ge=0.0)
    current_version: int = 1
    iteration_count: int = 0
    max_iterations: int = 5
    min_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def save(self) -> None:
        import os
        os.makedirs(".cineflow/projects", exist_ok=True)
        path = os.path.join(".cineflow/projects", f"{self.project_id}.json")
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2))
            
    @classmethod
    def load(cls, project_id: str) -> Optional['ProjectState']:
        import os
        path = os.path.join(".cineflow/projects", f"{project_id}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return cls.model_validate_json(f.read())
        return None

class RenderReceipt(BaseModel):
    project_id: str
    manifest_version: int
    manifest_hash: str
    artifact_path: str
    artifact_sha256: str
    render_job_id: str
    ffmpeg_exit_code: int
    executor_signature: str
    validated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "VALIDATED"
