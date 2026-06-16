from enum import StrEnum


class ContractStatus(StrEnum):
    UPLOADED = "uploaded"
    INDEXED = "indexed"
    ANALYZING = "analyzing"
    READY = "ready"
    FAILED = "failed"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
