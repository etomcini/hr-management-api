import factory

from app.core.security import hash_password
from app.users.models import User


class UserFactory(factory.Factory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")

    password_hash = factory.LazyFunction(lambda: hash_password("TestPassword123!"))

    is_active = True
