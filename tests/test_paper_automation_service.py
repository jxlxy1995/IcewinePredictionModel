from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from icewine_prediction.database import create_memory_database, create_session_factory, initialize_database
from icewine_prediction.models import PaperAutomationTask


BEIJING = ZoneInfo("Asia/Shanghai")


def test_initialize_database_creates_paper_automation_tasks_table():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        task = PaperAutomationTask(
            created_at=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
            updated_at=datetime(2026, 6, 15, 17, 0, tzinfo=BEIJING),
            created_by="web",
            trigger_at=datetime(2026, 6, 15, 18, 21, tzinfo=BEIJING),
            match_window_start=datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING),
            match_window_end=datetime(2026, 6, 15, 18, 30, tzinfo=BEIJING),
            status="pending",
            notification_status="pending",
        )
        session.add(task)
        session.commit()

        loaded = session.get(PaperAutomationTask, task.id)

    assert loaded is not None
    assert loaded.status == "pending"
    assert loaded.notification_status == "pending"
