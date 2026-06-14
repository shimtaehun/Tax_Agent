"""월마감 체크리스트 순수 로직 테스트."""

from tax_copilot.core.tax.monthly_closing import (
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    default_steps,
    overall_status,
    progress_ratio,
    set_step_done,
)


def test_default_steps_all_incomplete() -> None:
    steps = default_steps()
    assert len(steps) == 8
    assert all(not s.done for s in steps)
    assert progress_ratio(steps) == 0.0
    assert overall_status(steps) == STATUS_IN_PROGRESS


def test_set_step_done_marks_and_timestamps() -> None:
    steps = default_steps()
    updated = set_step_done(steps, "collect", True, now_iso="2026-06-14T10:00:00")
    target = next(s for s in updated if s.key == "collect")
    assert target.done is True
    assert target.done_at == "2026-06-14T10:00:00"


def test_unsetting_clears_timestamp() -> None:
    steps = set_step_done(default_steps(), "collect", True, now_iso="2026-06-14T10:00:00")
    steps = set_step_done(steps, "collect", False, now_iso="2026-06-14T11:00:00")
    target = next(s for s in steps if s.key == "collect")
    assert target.done is False
    assert target.done_at is None


def test_all_done_sets_status_done() -> None:
    steps = default_steps()
    for s in steps:
        steps = set_step_done(steps, s.key, True, now_iso="2026-06-14T10:00:00")
    assert progress_ratio(steps) == 1.0
    assert overall_status(steps) == STATUS_DONE


def test_unknown_key_is_noop() -> None:
    steps = default_steps()
    updated = set_step_done(steps, "does_not_exist", True, now_iso="2026-06-14T10:00:00")
    assert all(not s.done for s in updated)
