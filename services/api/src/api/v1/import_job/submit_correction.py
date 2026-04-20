"""Submit a user correction against an import item's inferred field.

efi-4. When the Review Import screen detects that a user edited a
field marked inferred (sparkle badge dismisses on first value change),
a 1500ms-debounced dispatch calls this endpoint with ``{field, corrected}``.
The server resolves the original value + was_inferred provenance from
``parsed_recipe`` and writes one ``error_logs`` audit row with
``service="audit"`` and ``error_type="InferredFieldCorrected"``.

The endpoint intentionally does NOT mutate ``parsed_recipe`` — the real
user edit flows through ``approve_import_item`` at save time. This is a
side-channel logging endpoint; the user never sees a spinner or error.

Response: 204 No Content on success. 4xx on validation / access errors.

Design principle 8 from the epic: the correction-log is the killer
feature. Every row here is one data point that says "the model guessed
X, the user wanted Y." Make the log comprehensive now even if the
dashboard that reads it doesn't exist yet.
"""

import json
from typing import Any

from pydantic import BaseModel
from utils.api.endpoint import APIException, Endpoint, failure, success
from utils.classes.error_code import ErrorCode
from utils.models.error_log import ErrorLog
from utils.models.import_item import ImportItem
from utils.models.import_job import ImportJob
from utils.models.user import User
from utils.services.recipe_extractors.inference_prompt import INFERABLE_FIELDS


class SubmitCorrection(Endpoint):
    """POST /v1/import-items/{id}/corrections — log a user override on an
    inferred field.

    Writes one ``error_logs`` row. Returns 204 on success. Never mutates
    ``parsed_recipe`` — approve-import-item is the real persistence path.
    """

    def execute(self, item_id: str, params: "SubmitCorrection.Params"):
        user: User = self.user

        if params.field not in INFERABLE_FIELDS:
            return failure(
                status=400,
                error_code=ErrorCode.VALIDATION_ERROR.value,
                error_message="field not inferable",
                data={"allowed": list(INFERABLE_FIELDS)},
            )

        item = self.database.find_by(ImportItem, id=item_id)
        if not item:
            raise APIException(
                status_code=404,
                detail=f"Import item with ID '{item_id}' not found",
                code=ErrorCode.IMPORT_ITEM_NOT_FOUND,
            )

        # Access check: owner of the parent ImportJob.
        job = self.database.find_by(ImportJob, id=item.import_job_id)
        if not job or job.user_id != user.id:
            raise APIException(
                status_code=403,
                detail="You don't have access to this import item",
                code=ErrorCode.IMPORT_JOB_ACCESS_DENIED,
            )

        parsed = item.parsed_recipe or {}
        original = parsed.get(params.field)
        inferred_list = parsed.get("inferred_fields") or []
        was_inferred = (
            isinstance(inferred_list, list) and params.field in inferred_list
        )

        metadata = {
            "field": params.field,
            "original": original,
            "corrected": params.corrected,
            "was_inferred": was_inferred,
        }

        row = ErrorLog(
            service="audit",
            error_type="InferredFieldCorrected",
            error_message=json.dumps(metadata, default=str, sort_keys=True),
            import_item_id=item.id,
            user_id=user.id,
        )
        self.database.db.add(row)
        self.database.db.commit()

        return success(data=SubmitCorrection.Response(), status=204)

    class Params(BaseModel):
        field: str
        corrected: Any = None

    class Response(BaseModel):
        pass
