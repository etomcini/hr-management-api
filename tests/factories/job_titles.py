import factory

from app.job_titles.models import JobTitle


class JobTitleFactory(factory.Factory):
    class Meta:
        model = JobTitle

    name = factory.Sequence(lambda n: f"test_job_title_{n}")

    description = factory.Sequence(lambda n: f"Test job title {n}")
