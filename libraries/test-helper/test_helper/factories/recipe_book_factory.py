from factory import Factory, Faker
from utils.models.recipe_book import RecipeBook


class RecipeBookFactory(Factory):
    """Factory for creating RecipeBook instances."""

    class Meta:
        model = RecipeBook

    id = Faker('uuid4')
    name = Faker('word')
    description = Faker('sentence')
    is_public = False
    archived_at = None
