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
        'DATABASE_URL': 'postgresql://postgres:postgres@localhost:5432/test',
        'ENVIRONMENT': 'test',
        'AWS_REGION': 'us-east-1',
        'OPENAI_API_KEY': 'test_openai_api_key',
        'AUTH0_DOMAIN': 'test.auth0.com',
        'AUTH0_AUDIENCE': 'https://api.palateful.test',
        'AUTH0_CLIENT_ID': 'test_client_id',
        'CELERY_BROKER_URL': 'sqs://',
        'CELERY_QUEUE_PREFIX': 'palateful-test-',
        'REDIS_URL': 'redis://localhost:6379/0',
    }
    for var, value in default_vars.items():
        os.environ.setdefault(var, value)
