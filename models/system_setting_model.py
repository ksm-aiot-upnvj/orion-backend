from datetime import UTC, datetime
import json
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from config.db import Base
from utils.uuid_utils import generate_uuid7


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid7)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)  # Stored as JSON serialized string
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    def get_json_value(self) -> dict[str, Any]:
        try:
            return json.loads(self.value)
        except Exception:
            return {}

    def set_json_value(self, data: dict[str, Any]) -> None:
        self.value = json.dumps(data, ensure_ascii=False)
