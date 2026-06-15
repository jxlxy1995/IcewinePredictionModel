from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from threading import Event, Thread
from typing import Callable

from sqlalchemy.orm import Session

from icewine_prediction.paper_automation_service import claim_due_paper_automation_task
from icewine_prediction.time_utils import now_beijing


logger = logging.getLogger(__name__)


def poll_paper_automation_once(
    session_factory: Callable[[], Session],
    *,
    now: datetime,
    grace_minutes: int,
    executor: Callable[[int], object],
) -> int | None:
    session = session_factory()
    try:
        task = claim_due_paper_automation_task(session, now=now, grace_minutes=grace_minutes)
        if task is None:
            return None
        task_id = task.id
    finally:
        session.close()

    executor(task_id)
    return task_id


@dataclass
class PaperAutomationScheduler:
    session_factory: Callable[[], Session]
    executor: Callable[[int], object]
    grace_minutes: int = 20
    poll_seconds: float = 20
    stop_timeout_seconds: float = 5
    clock: Callable[[], datetime] = now_beijing
    _stop_event: Event = field(default_factory=Event, init=False)
    _thread: Thread | None = field(default=None, init=False)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.stop_timeout_seconds)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                # The executor must finalize claimed task state on failure. The
                # real web executor uses execute_paper_automation_task for that.
                poll_paper_automation_once(
                    self.session_factory,
                    now=self.clock(),
                    grace_minutes=self.grace_minutes,
                    executor=self.executor,
                )
            except Exception:
                logger.exception("paper automation scheduler poll failed")
            self._stop_event.wait(self.poll_seconds)
