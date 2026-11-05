import pytest
from automation.history.models import History
from automation.scheduler.models import Scheduler
from django.core.management import call_command


class LongFailure:
    def execute(self):
        raise RuntimeError("x" * 1000)


@pytest.mark.django_db
def test_a_long_error_is_kept_in_the_history(monkeypatch):
    task = Scheduler.objects.create(
        name="failing.LongFailure", description="", active=True, recurrence="hourly"
    )
    monkeypatch.setattr(
        "mgmt.management.commands.automation.module_loading.import_string",
        lambda path: LongFailure,
    )

    call_command("automation", force=task.name)

    failure = History.objects.get(scheduler=task, status=2)
    assert len(failure.comment) == 255
    assert failure.comment.startswith(f"Task {task.name} failed")
    assert failure.comment.endswith("…")
