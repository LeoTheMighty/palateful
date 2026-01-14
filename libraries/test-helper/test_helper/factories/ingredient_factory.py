from factory import Factory, Faker
from utils.models.ingredient import Ingredient


class IngredientFactory(Factory):
    """Factory for creating Ingredient instances."""

    class Meta:
        model = Ingredient

    id = Faker('uuid4')
    canonical_name = Faker('word')
    aliases = []
    category = Faker('word')
    flavor_profile = []
    default_unit = 'g'
    is_canonical = True
    pending_review = False
    image_url = None
    embedding = None
    submitted_by_id = None
    parent_id = None
    archived_at = None
