"""Tests for drawing worker — automated lifecycle management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fittrack.workers.drawing_worker import DrawingWorker, DrawingWorkerResult

# ── Mock services ───────────────────────────────────────────────────


class MockDrawingService:
    def __init__(self, drawings: list[dict[str, Any]] | None = None) -> None:
        self.drawing_repo = MockDrawingRepo(drawings)
        self._closed: list[str] = []
        self._close_error: str | None = None

    def check_sales_should_close(self, drawing_id: str, now: datetime) -> bool:
        d = self.drawing_repo.find_by_id(drawing_id)
        if d is None or d.get("status") != "open":
            return False
        draw_time = d.get("drawing_time")
        if draw_time is None:
            return False
        if isinstance(draw_time, str):
            draw_time = datetime.fromisoformat(draw_time)
        if draw_time.tzinfo is None:
            draw_time = draw_time.replace(tzinfo=UTC)
        close_time = draw_time - timedelta(minutes=5)
        return now >= close_time

    def close_drawing(self, drawing_id: str) -> dict[str, Any]:
        if self._close_error:
            raise RuntimeError(self._close_error)
        d = self.drawing_repo.find_by_id(drawing_id)
        d["status"] = "closed"
        self._closed.append(drawing_id)
        return d

    def check_drawing_ready(self, drawing_id: str, now: datetime) -> bool:
        d = self.drawing_repo.find_by_id(drawing_id)
        if d is None or d.get("status") != "closed":
            return False
        draw_time = d.get("drawing_time")
        if draw_time is None:
            return False
        if isinstance(draw_time, str):
            draw_time = datetime.fromisoformat(draw_time)
        if draw_time.tzinfo is None:
            draw_time = draw_time.replace(tzinfo=UTC)
        return now >= draw_time


class MockDrawingRepo:
    def __init__(self, drawings: list[dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        for d in drawings or []:
            self._store[d["drawing_id"]] = dict(d)

    def find_by_id(self, drawing_id: str) -> dict[str, Any] | None:
        return self._store.get(drawing_id)

    def find_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        return [d for d in self._store.values() if d.get(field) == value]


class MockDrawingExecutor:
    def __init__(self) -> None:
        self._executed: list[str] = []
        self._error: str | None = None

    def execute(self, drawing_id: str) -> dict[str, Any]:
        if self._error:
            raise RuntimeError(self._error)
        self._executed.append(drawing_id)
        return {"drawing_id": drawing_id, "status": "completed"}


# ── DrawingWorkerResult tests ───────────────────────────────────────


class TestWorkerResult:
    def test_empty_result_is_success(self):
        r = DrawingWorkerResult()
        assert r.success is True

    def test_result_with_errors(self):
        r = DrawingWorkerResult()
        r.errors.append("something failed")
        assert r.success is False

    def test_to_dict(self):
        r = DrawingWorkerResult()
        r.sales_closed.append("d1")
        r.drawings_executed.append("d2")
        d = r.to_dict()
        assert d["sales_closed"] == ["d1"]
        assert d["drawings_executed"] == ["d2"]
        assert d["success"] is True


# ── Worker run tests ────────────────────────────────────────────────


class TestWorkerRun:
    def test_no_drawings(self):
        svc = MockDrawingService([])
        executor = MockDrawingExecutor()
        worker = DrawingWorker(drawing_service=svc, drawing_executor=executor)
        result = worker.run()
        assert result.success is True
        assert result.sales_closed == []
        assert result.drawings_executed == []

    def test_close_sales_at_t_minus_5(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        drawings = [{
            "drawing_id": "d1",
            "status": "open",
            "drawing_time": draw_time.isoformat(),
        }]
        svc = MockDrawingService(drawings)
        executor = MockDrawingExecutor()
        worker = DrawingWorker(drawing_service=svc, drawing_executor=executor)

        now = datetime(2026, 3, 1, 17, 55, tzinfo=UTC)
        result = worker.run(now)
        assert "d1" in result.sales_closed
        assert result.success is True

    def test_no_close_before_t_minus_5(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        drawings = [{
            "drawing_id": "d1",
            "status": "open",
            "drawing_time": draw_time.isoformat(),
        }]
        svc = MockDrawingService(drawings)
        executor = MockDrawingExecutor()
        worker = DrawingWorker(drawing_service=svc, drawing_executor=executor)

        now = datetime(2026, 3, 1, 17, 50, tzinfo=UTC)
        result = worker.run(now)
        assert result.sales_closed == []

    def test_execute_ready_drawing(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        drawings = [{
            "drawing_id": "d1",
            "status": "closed",
            "drawing_time": draw_time.isoformat(),
        }]
        svc = MockDrawingService(drawings)
        executor = MockDrawingExecutor()
        worker = DrawingWorker(drawing_service=svc, drawing_executor=executor)

        now = datetime(2026, 3, 1, 18, 1, tzinfo=UTC)
        result = worker.run(now)
        assert "d1" in result.drawings_executed
        assert result.success is True

    def test_no_execute_before_draw_time(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        drawings = [{
            "drawing_id": "d1",
            "status": "closed",
            "drawing_time": draw_time.isoformat(),
        }]
        svc = MockDrawingService(drawings)
        executor = MockDrawingExecutor()
        worker = DrawingWorker(drawing_service=svc, drawing_executor=executor)

        now = datetime(2026, 3, 1, 17, 59, tzinfo=UTC)
        result = worker.run(now)
        assert result.drawings_executed == []

    def test_multiple_drawings_in_one_cycle(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        drawings = [
            {
                "drawing_id": "d1",
                "status": "open",
                "drawing_time": draw_time.isoformat(),
            },
            {
                "drawing_id": "d2",
                "status": "closed",
                "drawing_time": draw_time.isoformat(),
            },
        ]
        svc = MockDrawingService(drawings)
        executor = MockDrawingExecutor()
        worker = DrawingWorker(drawing_service=svc, drawing_executor=executor)

        now = datetime(2026, 3, 1, 18, 1, tzinfo=UTC)
        result = worker.run(now)
        assert "d1" in result.sales_closed
        assert "d2" in result.drawings_executed

    def test_execution_error_captured(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        drawings = [{
            "drawing_id": "d1",
            "status": "closed",
            "drawing_time": draw_time.isoformat(),
        }]
        svc = MockDrawingService(drawings)
        executor = MockDrawingExecutor()
        executor._error = "boom"
        worker = DrawingWorker(drawing_service=svc, drawing_executor=executor)

        now = datetime(2026, 3, 1, 18, 1, tzinfo=UTC)
        result = worker.run(now)
        assert result.success is False
        assert len(result.errors) == 1

    def test_close_error_captured(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        drawings = [{
            "drawing_id": "d1",
            "status": "open",
            "drawing_time": draw_time.isoformat(),
        }]
        svc = MockDrawingService(drawings)
        svc._close_error = "close failed"
        executor = MockDrawingExecutor()
        worker = DrawingWorker(drawing_service=svc, drawing_executor=executor)

        now = datetime(2026, 3, 1, 17, 55, tzinfo=UTC)
        result = worker.run(now)
        assert result.success is False
