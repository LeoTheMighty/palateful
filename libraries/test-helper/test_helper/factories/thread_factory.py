from factory import Factory, Faker, SubFactory, LazyAttribute
from utils.models.thread import Thread


class ThreadFactory(Factory):
    """Factory for creating Thread instances."""

    class Meta:
        model = Thread
        exclude = ['user']

    id = Faker('uuid4')
    title = Faker('sentence')
    user = SubFactory('test_helper.factories.user_factory.UserFactory')
    user_id = LazyAttribute(lambda o: o.user.id)
    archived_at = None
