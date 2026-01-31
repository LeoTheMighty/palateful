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

    # API Error
    API_ERROR = 32

    # Webhook Error
    WEBHOOK_ERROR = 33

    # Unexpected API output - output from an API, tool, or agent is malformed or not as expected.
    UNEXPECTED_API_OUTPUT = 34

    # Service not supported
    SERVICE_NOT_SUPPORTED = 35

    # Unsupported item type
    UNSUPPORTED_ITEM_TYPE = 36

    # Invalid request - The request parameters are invalid or malformed
    INVALID_REQUEST = 37

    # Auth errors (40-49)
    INVALID_TOKEN = 40
    TOKEN_EXPIRED = 41
    USER_NOT_FOUND = 42
    UNAUTHORIZED = 43
    FORBIDDEN = 44

    # Recipe Book errors (100-109)
    RECIPE_BOOK_NOT_FOUND = 100
    RECIPE_BOOK_ACCESS_DENIED = 101
    DUPLICATE_RECIPE_BOOK_NAME = 102

    # Recipe errors (110-119)
    RECIPE_NOT_FOUND = 110
    RECIPE_ACCESS_DENIED = 111
    DUPLICATE_RECIPE_NAME = 112

    # Ingredient errors (120-129)
    INGREDIENT_NOT_FOUND = 120
    DUPLICATE_INGREDIENT = 121
    INVALID_INGREDIENT_QUANTITY = 122

    # Meal Event errors (130-139)
    MEAL_EVENT_NOT_FOUND = 130
    MEAL_EVENT_ACCESS_DENIED = 131
    MEAL_EVENT_INVALID_STATUS = 132
    MEAL_EVENT_PARTICIPANT_NOT_FOUND = 133
    MEAL_EVENT_ALREADY_PARTICIPANT = 134

    # Shopping List errors (140-149)
    SHOPPING_LIST_NOT_FOUND = 140
    SHOPPING_LIST_ACCESS_DENIED = 141
    SHOPPING_LIST_ITEM_NOT_FOUND = 142

    # Timer errors (150-159)
    TIMER_NOT_FOUND = 150
    TIMER_INVALID_STATUS = 151
    TIMER_ALREADY_COMPLETED = 152

    # Import errors (160-179)
    IMPORT_JOB_NOT_FOUND = 160
    IMPORT_JOB_ACCESS_DENIED = 161
    IMPORT_JOB_INVALID_STATUS = 162
    IMPORT_JOB_CANCELLED = 163
    IMPORT_ITEM_NOT_FOUND = 164
    IMPORT_ITEM_INVALID_STATUS = 165
    IMPORT_EXTRACTION_FAILED = 166
    IMPORT_URL_FETCH_FAILED = 167
    IMPORT_INVALID_SOURCE_TYPE = 168
    IMPORT_NO_RECIPE_DATA = 169
    IMPORT_INGREDIENT_MATCH_FAILED = 170

    # Shopping List Sharing errors (180-199)
    SHOPPING_LIST_NOT_SHARED = 180
    SHOPPING_LIST_ALREADY_MEMBER = 181
    SHOPPING_LIST_INVALID_SHARE_CODE = 182
    SHOPPING_LIST_CANNOT_REMOVE_OWNER = 183
    SHOPPING_LIST_MEMBER_NOT_FOUND = 184
    SHOPPING_LIST_SHARE_LIMIT_REACHED = 185
    SHOPPING_LIST_CANNOT_LEAVE_AS_OWNER = 186

    # General errors (200-219)
    NOT_FOUND = 200
    VALIDATION_ERROR = 201
    CONFLICT = 202
    RATE_LIMITED = 203

    # Friends/Social errors (220-239)
    FRIEND_REQUEST_NOT_FOUND = 220
    FRIENDSHIP_NOT_FOUND = 221
    ALREADY_FRIENDS = 222
    FRIEND_REQUEST_ALREADY_SENT = 223
    FRIEND_REQUEST_ALREADY_RECEIVED = 224
    CANNOT_FRIEND_SELF = 225
    USERNAME_TAKEN = 226
    USERNAME_INVALID = 227
    USERNAME_RESERVED = 228
    USERNAME_CHANGE_COOLDOWN = 229
