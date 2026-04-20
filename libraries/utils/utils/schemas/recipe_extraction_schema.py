"""Standard JSON schema for recipe extraction output.

All recipe extractors (JSON-LD, AI, text, video, audio, PDF) must produce
output conforming to this schema. The schema is the single source of truth
for the shape of ``parsed_recipe`` stored on ``ImportItem``.
"""

from __future__ import annotations

RECIPE_EXTRACTION_SCHEMA: dict = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": ["number", "string", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "notes": {"type": ["string", "null"]},
                    "is_optional": {"type": "boolean"},
                },
            },
        },
        "instructions": {"type": ["string", "null"]},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "instruction": {"type": "string"},
                    "order": {"type": "integer"},
                    # cmt-1 — actively-tended durations the cook will time in
                    # cook-mode. Validation is deliberately permissive here;
                    # `create_recipe_task` clamps/filters at persist time.
                    "timers": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "duration_minutes": {"type": "integer"},
                                "label": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
        "prep_time_minutes": {"type": ["integer", "null"]},
        "cook_time_minutes": {"type": ["integer", "null"]},
        "servings": {"type": ["integer", "null"]},
        "tags": {"type": "array", "items": {"type": "string"}},
        "source_url": {"type": ["string", "null"]},
        "image_url": {"type": ["string", "null"]},
        "primary_vibe": {"type": ["string", "null"]},
        "secondary_vibe": {"type": ["string", "null"]},
        # irrd-3 — self-reported model score or heuristic fallback.
        # `null` is a legitimate value ("model declined, heuristic has
        # not yet run"); the extract_recipe_task pipeline resolves it
        # before persistence so persisted parsed_recipe JSONB always
        # carries a numeric score paired with a source label.
        "confidence_score": {"type": ["number", "null"]},
        "confidence_source": {"type": ["string", "null"]},
        # efi-2 — names of inferable recipe-root fields the extractor
        # best-guessed rather than pulled from the source. Permissive:
        # no ``items.enum`` restriction here (the INFERABLE_FIELDS
        # allow-list is enforced in extractor parsing + server-side
        # guardrails, not the schema). Always-present array contract
        # lives in the prompt; the schema just documents the shape.
        "inferred_fields": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_extraction_result(data: dict) -> tuple[bool, list[str]]:
    """Validate an extraction result dict against the standard schema.

    Attempts to use the ``jsonschema`` library for full JSON Schema
    validation.  If ``jsonschema`` is not installed, falls back to a
    lightweight manual check of required fields and top-level types.

    Args:
        data: The recipe extraction dict to validate.

    Returns:
        A ``(is_valid, errors)`` tuple where *is_valid* is ``True`` when
        there are zero errors and *errors* is a list of human-readable
        error strings.
    """
    try:
        import jsonschema  # noqa: F811

        return _validate_with_jsonschema(data, jsonschema)
    except ImportError:
        return _validate_manually(data)


# ---------------------------------------------------------------------------
# jsonschema-backed validation
# ---------------------------------------------------------------------------

def _validate_with_jsonschema(data: dict, jsonschema_mod) -> tuple[bool, list[str]]:
    """Validate using the ``jsonschema`` library."""
    validator = jsonschema_mod.Draft7Validator(RECIPE_EXTRACTION_SCHEMA)
    raw_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    errors = [_format_jsonschema_error(e) for e in raw_errors]
    return (len(errors) == 0, errors)


def _format_jsonschema_error(error) -> str:
    """Format a ``jsonschema.ValidationError`` into a readable string."""
    path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
    return f"{path}: {error.message}"


# ---------------------------------------------------------------------------
# Manual fallback validation
# ---------------------------------------------------------------------------

_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


def _validate_manually(data: dict) -> tuple[bool, list[str]]:
    """Lightweight validation without jsonschema."""
    errors: list[str] = []

    if not isinstance(data, dict):
        return (False, ["Expected a JSON object at root"])

    # Required fields
    for field in RECIPE_EXTRACTION_SCHEMA.get("required", []):
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    properties = RECIPE_EXTRACTION_SCHEMA.get("properties", {})

    for key, value in data.items():
        if key not in properties:
            # Extra fields are allowed (no additionalProperties: false)
            continue
        prop_schema = properties[key]
        _check_type(errors, key, value, prop_schema)

    return (len(errors) == 0, errors)


def _check_type(errors: list[str], path: str, value, schema: dict) -> None:
    """Check a single value against its property schema."""
    type_spec = schema.get("type")
    if type_spec is None:
        return

    allowed_types: list[str] = type_spec if isinstance(type_spec, list) else [type_spec]
    python_types = tuple(
        t for name in allowed_types for t in ((_TYPE_MAP[name],) if isinstance(_TYPE_MAP.get(name), type) else (_TYPE_MAP.get(name) or ()))  # type: ignore[arg-type]
    )

    if not python_types:
        return

    if not isinstance(value, python_types):
        errors.append(
            f"'{path}' expected type {allowed_types} but got {type(value).__name__}"
        )
        return

    # Recurse into arrays
    if isinstance(value, list) and "items" in schema:
        item_schema = schema["items"]
        for idx, item in enumerate(value):
            item_path = f"{path}[{idx}]"
            item_type = item_schema.get("type")
            if item_type:
                _check_type(errors, item_path, item, item_schema)
            # Check required fields on object items
            if isinstance(item, dict):
                for req in item_schema.get("required", []):
                    if req not in item:
                        errors.append(f"'{item_path}': missing required field '{req}'")
                # Check nested property types
                for prop_name, prop_schema in item_schema.get("properties", {}).items():
                    if prop_name in item:
                        _check_type(errors, f"{item_path}.{prop_name}", item[prop_name], prop_schema)
