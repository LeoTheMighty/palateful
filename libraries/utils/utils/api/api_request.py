import json
from typing import Any, Generic, Optional, TypeVar, Type, Union
from pydantic import BaseModel, Field, model_validator
from utils.classes.service import Service
from utils.services.helpers.encoder import CustomEncoder
from starlette.datastructures import QueryParams

T = TypeVar('T', bound=BaseModel)

def parse_dict(params: Union[dict, list]) -> Union[dict, list]:
    """
    Deeply parse dictionary values, converting string JSON into Python objects.
    Only converts strings that look like JSON objects/arrays.
    String numbers remain as strings.
    
    Args:
        params (dict|list): Dictionary or list of query parameters
        
    Returns:
        dict|list: Parsed dictionary/list with JSON strings converted to Python objects
    """
    if isinstance(params, list):
        return [parse_dict(item) if isinstance(item, (dict, list)) else item
                for item in params]

    parsed = {}
    for key, value in params.items():
        if isinstance(value, str):
            try:
                parsed_value = json.loads(value)
                # Only convert if the parsed value is a complex type (dict/list)
                if isinstance(parsed_value, (dict, list)):
                    parsed[key] = parse_dict(parsed_value)  # Recursively parse the result
                else:
                    # Keep original string for simple types (including numbers)
                    parsed[key] = value
            except (json.JSONDecodeError, TypeError):
                parsed[key] = value
        elif isinstance(value, (dict, list)):
            parsed[key] = parse_dict(value)
        else:
            parsed[key] = value
    return parsed


# TODO: We need to make this for Auth0 and changed for palateful
class APIRequest(BaseModel, Generic[T]):
    """Model for any API request"""
    user_uuid: str = Field(..., description="Unique identifier for the user making the request")
    service: Service
    merchant_uuid: Optional[str] = Field(None,
                                         description="Unique identifier for the "
                                                     "merchant (law firm)")
    stream_channel: Optional[str] = Field(None,
                                          description="Channel identifier for streaming responses")
    location: Optional[str] = Field(None,
                                    description="Location the API request was made from"
                                                " for product analytics")
    stream: Optional[bool] = True
    catalyst_id: Optional[str] = Field(None, description="Unique identifier for the catalyst")
    data: Optional[T] = Field(None, description="Payload data specific to the endpoint")

    @model_validator(mode='before')
    @classmethod
    def handle_tenant_uuid_alias(cls, data: Any) -> Any:
        """Convert tenant_uuid to merchant_uuid for backwards compatibility.

        merchant_uuid takes precedence if both are provided.
        """
        if isinstance(data, dict):
            tenant_uuid = data.pop('tenant_uuid', None)
            if tenant_uuid is not None and data.get('merchant_uuid') is None:
                data['merchant_uuid'] = tenant_uuid
        return data

    @property
    def tenant_uuid(self) -> Optional[str]:
        """Backwards compatibility alias for merchant_uuid (deprecated)."""
        return self.merchant_uuid

    @classmethod
    def from_json(cls: Type['APIRequest'], json_str: str) -> 'APIRequest':
        """Create an instance of the Pydantic model from a JSON string."""
        return cls.parse_raw(json_str)

    @classmethod
    def from_query_params(cls: Type['APIRequest'], query_params: QueryParams) -> 'APIRequest':
        """Create an instance of the Pydantic model from query parameters."""
        query_params = parse_dict(query_params)

        # Support both merchant_uuid and tenant_uuid for backwards compatibility
        # merchant_uuid takes precedence if both are provided
        tenant_uuid_value = query_params.pop('tenant_uuid', None)
        merchant_uuid_value = query_params.pop('merchant_uuid', None)
        resolved_merchant_uuid = merchant_uuid_value or tenant_uuid_value

        request = {
            'user_uuid': query_params.pop('user_uuid', None),
            'service': query_params.pop('service', None),
            'merchant_uuid': resolved_merchant_uuid,
            'stream_channel': query_params.pop('stream_channel', None),
            'location': query_params.pop('location', None),
            'stream': query_params.pop('stream', None),
            'catalyst_id': query_params.pop('catalyst_id', None),
            'data': query_params  # Rest of query goes to data
        }

        return cls(**request)

    def to_json(self: 'APIRequest') -> str:
        """Convert the current instance to a JSON string."""
        data = {
            'user_uuid': self.user_uuid,
            'service': self.service,
            'merchant_uuid': self.merchant_uuid,
            'stream_channel': self.stream_channel,
            'location': self.location,
            'stream': self.stream,
            'catalyst_id': self.catalyst_id,
        }

        # Handle data field - will be either None or a BaseModel
        if self.data is not None:
            if hasattr(self.data, 'model_dump'):
                try:
                    data['data'] = self.data.model_dump()
                except Exception:
                    data['data'] = dict(self.data)  # Fallback if model_dump fails
            else:
                data['data'] = dict(self.data)
        else:
            data['data'] = None

        return CustomEncoder().encode(data)
