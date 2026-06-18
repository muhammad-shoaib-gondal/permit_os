from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    FINDING = "finding"
    COMPLETE = "complete"
    QUESTION = "question"
    CONFLICT = "conflict"
    EVENT = "event"
    DISPATCH = "dispatch"


class Citation(BaseModel):
    source: str
    url: Optional[str] = None


class BandMessage(BaseModel):
    type: MessageType
    case_id: UUID
    agent: str
    timestamp: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)

    def to_json_block(self) -> str:
        import json

        return json.dumps(self.model_dump(mode="json"), indent=2)
