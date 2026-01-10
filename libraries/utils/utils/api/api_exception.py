from fastapi import HTTPException
from utils.classes.error_code import ErrorCode


class APIException(HTTPException):
    """
    Custom exception class to standardize error handling across the API.

    This exception extends FastAPI's HTTPException by adding a custom error code and an optional
    user-friendly error message.

    Attributes:
        status_code (int): HTTP status code that should be returned.
        detail (str): Technical description of the error.
        code (int): Custom application-specific error code. Defaults to 1.

    OpenAI Python Error Codes:
        https://platform.openai.com/docs/guides/error-codes/python-library-error-types
    Error Codes:
        1: "Internal error" - Default error code.
        2: "Document too large" - Document exceeds the allowed byte size.
        3: "Document too long" - Document exceeds the allowed character count.
        4: "OpenAI APIConnectionError" - Issue connecting to OpenAI services.
        5: "OpenAI APITimeoutError" - Request timed out. Retryable.
        6: "OpenAI AuthenticationError" - Invalid, expired, or revoked API key or token.
        7: "OpenAI BadRequestError" - Malformed request or missing required parameters.
        8: "OpenAI ConflictError" - Resource was updated by another request.
        9: "OpenAI InternalServerError" - Issue on OpenAI's side. Retryable.
        10: "OpenAI NotFoundError" - Requested resource does not exist.
        11: "OpenAI PermissionDeniedError" - Lack of access to the requested resource.
        12: "OpenAI RateLimitError" - Rate limit exceeded. Retryable.
        13: "OpenAI UnprocessableEntityError" -
                Unable to process request despite correct format. Retryable.
        14. "OpenAI Error" - General OpenAI error.
        15: "S3 error" - Error response from Amazon S3 service.
        16: "Invalid summary data type" - The provided data type is not valid for summarization.
        17: "Invalid summary strategy" - The provided summarization strategy is not valid.
        18: "SQS failure" - Error response from the Amazon SQS service.
        19: "Invalid endpoint result" - The result of the endpoint is not valid.
        20: "Invalid document content" - The provided document content is not valid.
        21: "Token limit exceeded" - The token limit for the context window has been exceeded.

    Example Usage:
        ```
        except Exception as e:
            logger.error(e)
            raise APIException(status_code=500, detail="Document too large", code=2) from e
        ```
    """
    def __init__(self, status_code: int, detail: str, code: ErrorCode = ErrorCode.INTERNAL_ERROR):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code.value

    def __reduce__(self):
        return self.__class__, (self.status_code, self.detail, ErrorCode.from_value(self.code))

    def __str__(self):
        return f"APIException(code = {self.code}): {self.detail}"
