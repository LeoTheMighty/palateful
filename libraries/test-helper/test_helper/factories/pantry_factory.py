from factory import Factory, Faker
from utils.models.pantry import Pantry


class PantryFactory(Factory):
    """Factory for creating Pantry instances."""

    class Meta:
        model = Pantry

    id = Faker('uuid4')
    name = Faker('word')
    archived_at = None
