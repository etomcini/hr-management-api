import factory

from app.departments.models import Department


class DepartmentFactory(factory.Factory):
    class Meta:
        model = Department

    name = factory.Sequence(lambda n: f"test_department_{n}")

    code = factory.Sequence(lambda n: f"CD{n}")
