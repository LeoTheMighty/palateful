from factory import Factory, Faker, LazyAttribute
from utils.models.user import User


class UserFactory(Factory):
    """Factory for creating User instances."""

    class Meta:
        model = User

    id = Faker('uuid4')
    auth0_id = LazyAttribute(lambda o: f"auth0|{o.id}")
    email = Faker('email')
    name = Faker('name')
    picture = Faker('image_url')
    email_verified = True
    has_completed_onboarding = False
    archived_at = None
