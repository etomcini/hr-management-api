import factory

from app.roles.models import Role


class RoleFactory(factory.Factory):
    class Meta:
        model = Role

    name = factory.Sequence(lambda n: f"test_role_{n}")

    description = factory.Sequence(lambda n: f"Test role {n}")
