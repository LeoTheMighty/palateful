import json
import uuid
import datetime
from pydantic import BaseModel
from sqlalchemy import UUID

from hal_utils.classes.enum import BaseEnum

class CustomEncoder(json.JSONEncoder):
    """Custom Encoder for serializing `hal_utils` objects to JSON."""

    def default(self, obj):
        if isinstance(obj, BaseEnum):
            return obj.value
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, (UUID, uuid.UUID)):
            return str(obj)
        if isinstance(obj, Exception):
            return str(obj)
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        return json.JSONEncoder.default(self, obj)
