from utils.api.endpoint import Endpoint, success


class CreateUser(Endpoint):
    """Create a new user."""

    def execute(self):
        """Execute the endpoint."""
        return success(message="User created")

    class Params(BaseModel):
        """Params for the endpoint."""
        name: str
        email: str
        password: str

    class Response(BaseModel):
        """Response for the endpoint."""
        message: str