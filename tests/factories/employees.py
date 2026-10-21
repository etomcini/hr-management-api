from datetime import date

import factory

from app.employees.models import Employee


class EmployeeFactory(factory.Factory):
    class Meta:
        model = Employee

    employee_number = factory.Sequence(lambda n: f"EMP-{n:04d}")

    first_name = factory.Sequence(lambda n: f"EmployeeFirst{n}")

    last_name = factory.Sequence(lambda n: f"EmployeeLast{n}")

    hire_date = factory.LazyFunction(date.today)
