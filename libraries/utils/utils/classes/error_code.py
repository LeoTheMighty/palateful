from enum import unique
from utils.classes.enum import BaseEnum


@unique
class ErrorCode(BaseEnum):
    """
    Enum for all possible error codes.
    """
    # "Internal error" - Default error code.
    INTERNAL_ERROR = 1

    # "Document too large" - Document exceeds the allowed byte size.
    DOCUMENT_TOO_LARGE = 2

    # "Document too long" - Document exceeds the allowed character count.
    DOCUMENT_TOO_LONG = 3

    # "OpenAI APIConnectionError" - Issue connecting to OpenAI services.
    OPENAI_API_CONNECTION_ERROR = 4

    # "OpenAI APITimeoutError" - Request timed out. Retryable.
    OPENAI_API_TIMEOUT_ERROR = 5

    # "OpenAI AuthenticationError" - Invalid, expired, or revoked API key or token.
    OPENAI_AUTHENTICATION_ERROR = 6

    # "OpenAI BadRequestError" - Malformed request or missing required parameters.
    OPENAI_BAD_REQUEST_ERROR = 7

    # "OpenAI ConflictError" - Resource was updated by another request.
    OPENAI_CONFLICT_ERROR = 8

    # "OpenAI InternalServerError" - Issue on OpenAI's side. Retryable.
    OPENAI_INTERNAL_SERVER_ERROR = 9

    # "OpenAI NotFoundError" - Requested resource does not exist.
    OPENAI_NOT_FOUND_ERROR = 10

    # "OpenAI PermissionDeniedError" - Lack of access to the requested resource.
    OPENAI_PERMISSION_DENIED_ERROR = 11

    # "OpenAI RateLimitError" - Rate limit exceeded. Retryable.
    OPENAI_RATE_LIMIT_ERROR = 12

    # "OpenAI UnprocessableEntityError" - Unable to process request despite proper format.
    # Retryable.
    OPENAI_UNPROCESSABLE_ENTITY_ERROR = 13

    # "OpenAI Error" - General OpenAI error.
    OPENAI_GENERAL_ERROR = 14

    # "S3 error" - Error response from Amazon S3 service.
    S3_ERROR = 15

    # "Invalid summary data type" - The provided data type is not valid for summarization.
    INVALID_SUMMARY_DATA_TYPE = 16

    # "Invalid summary strategy" - The provided summarization strategy is not valid.
    INVALID_SUMMARY_STRATEGY = 17

    # "SQS failure" - Error response from the Amazon SQS service.
    SQS_FAILURE = 18

    # "Invalid endpoint result" - The result of the endpoint is not valid.
    INVALID_ENDPOINT_RESULT = 19

    # "Invalid document content" - The provided summary content is not valid.
    INVALID_DOCUMENT_CONTENT = 20

    # "Token limit exceeded" - The token limit for the context window has been exceeded.
    TOKEN_LIMIT_EXCEEDED = 21

    # "DB Rollback Error" - The transaction failed causing a DB rollback.
    DB_ROLLBACK_ERROR = 22

    # "Invalid Language Code" - The provided language code is not valid.
    INVALID_LANGUAGE_CODE = 23

    # "Database Lock Error" - Error acquiring a lock on the database.
    DATABASE_LOCK_ERROR = 24

    # "Failed to start step function" - Error starting the step function.
    FAILED_TO_START_STEP_FUNCTION = 25

    # Failed to parse the document
    DOCUMENT_PARSE_ERROR = 26

    # Document Is Scanned Error
    DOCUMENT_IS_SCANNED = 27

    # Thread not found Error
    THREAD_NOT_FOUND = 28

    # Chat not found Error
    CHAT_NOT_FOUND = 29

    # Summary not found Error
    SUMMARY_NOT_FOUND = 30

    # Document not found Error
    DOCUMENT_NOT_FOUND = 31

    # MyCase API Error
    MYCASE_API_ERROR = 32

    # MyCase Webhook Error
    MYCASE_WEBHOOK_ERROR = 33

    # Unexpected API output - output from an API, tool, or agent is malformed or not as expected.
    UNEXPECTED_API_OUTPUT = 34

    # Service not supported
    SERVICE_NOT_SUPPORTED = 35

    # Unsupported item type
    UNSUPPORTED_ITEM_TYPE = 36

    # Invalid request - The request parameters are invalid or malformed
    INVALID_REQUEST = 37
