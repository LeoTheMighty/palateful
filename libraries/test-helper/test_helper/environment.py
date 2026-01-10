import os


def setup_environment():
    """
    Setup default environment variables for tests.

    If you want to change these, then you have to change them manually and then
    dynamically import the file in your test.

    Example:

    ```python
    def test():
        os.environ['KEY'] = VALUE
        from main import app

        client = TestClient(app)
        assert client.get('/').status_code == 200
    ```
    """

    default_vars = {
        'OPENAI_ORGANIZATION': 'test_openai_org',
        'COURT_CASE_SUMMARY_GPT_MODEL': 'gpt-4o',
        'DOCUMENT_SUMMARY_GPT_MODEL': 'gpt-4o',
        'DOCUMENT_MAX_CHARACTER_COUNT': '40000',
        'S3_DOCUMENT_BUCKET_NAME': 'test_s3_document_bucket_name',
        'SQS_RESPONSE_QUEUE': 'test_sqs_response_queue',
        'SQS_MAX_RETRIES': '5',
        'SQS_MAX_DELAY': '30',
        'DEFAULT_GPT_MODEL': 'gpt-5',
        'DEFAULT_AGENT_MODEL': 'gpt-5',
        'CHAT_MESSAGE_MODEL': 'gpt-5',
        'STREAM_INTERVAL_SECONDS': '0.1',
        'APPSYNC_URI': 'test_appsync_uri',
        'OPENAI_API_KEY': 'test_openai_api_key',
        'DATABASE_URL': 'postgresql://hal:password@localhost:5432/test',
        'SUMMARY_STEP_FUNCTION_ARN': 'test_summary_step_function_arn',
        'S3_ACCESS_MYCASE_ACCOUNT_ROLE_ARN': 'test_s3_access_mycase_account_role_arn',
        'SQS_ACCESS_MYCASE_ACCOUNT_ROLE_ARN': 'test_s3_access_mycase_account_role_arn',
        'AWS_REGION': 'us-east-1',
        'FASTAPI_ENV': 'development',
        'GITHUB_ACTIONS': 'false',
        'MYCASE_EXTERNAL_INTEGRATIONS_API_URL': 'https://external.mycase.test',
        'MAX_CHAT_HISTORY': '10',
        'CHAT_RETRY_SECONDS': '900', # 15 minutes
        'MYCASE_WEBHOOK_URL': 'https://webhook.mycase.test',
        'MYCASE_API_PAGE_SIZE': '100',
        'ENVIRONMENT': 'test',
        'VECTOR_DATABASE': 'pinecone',
        'VECTOR_INDEX_REGION': 'us-east-1',
        'DOCUMENT_EMBEDDING_MODEL': 'text-embedding-3-small',
        'EMBEDDING_CHUNK_SIZE': '1000',
        'EMBEDDING_CHUNK_OVERLAP': '200',
        'PINECONE_API_KEY': 'test_pinecone_api_key',
        'PINECONE_METRIC': 'cosine',
        'VECTOR_TOP_K': '20',
        'VECTOR_RERANK_TOP_N': '5',
        'RERANKER_MODEL': 'cohere-rerank-3.5',
        'ENABLE_RERANKING': 'true',
        'VECTOR_DATABASE_DOCUMENT_INDEX': 'documents',
        'MIN_BATCH_SIZE': '2',
        'MAX_BATCH_SIZE': '10',
    }
    for var, value in default_vars.items():
        os.environ[var] = value
