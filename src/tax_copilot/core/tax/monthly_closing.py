"""고객사 월마감 체크리스트 순수 로직.

고객사마다 매달 반복되는 마감 절차(자료수집→검토→대사→집계→신고)를 표준
템플릿으로 만들고 진행률을 계산한다. core/ 레이어이므로 표준 라이브러리 +
pydantic만 사용한다.
"""

from __future__ import annotations

from pydantic import BaseModel

STATUS_IN_PROGRESS = "in_progress"
STATUS_DONE = "done"

# 월마감 표준 단계 (key, 표시명) — 실무 흐름 순서.
DEFAULT_STEPS: list[tuple[str, str]] = [
    ("collect", "자료 수집(영수증·카드·통장·세금계산서)"),
    ("review_receipts", "영수증 검토·승인"),
    ("classify", "계정과목 분류 확정"),
    ("reconcile", "카드·통장 대사"),
    ("missing_evidence", "누락 증빙 요청·확인"),
    ("vat_aggregate", "부가세 집계"),
    ("journal_export", "분개 생성·회계프로그램 반영"),
    ("file_return", "신고"),
]


class ClosingStep(BaseModel):
    key: str
    label: str
    done: bool = False
    done_at: str | None = None  # ISO datetime


def default_steps() -> list[ClosingStep]:
    """표준 마감 단계 목록을 미완료 상태로 생성한다."""
    return [ClosingStep(key=key, label=label) for key, label in DEFAULT_STEPS]


def progress_ratio(steps: list[ClosingStep]) -> float:
    """완료 비율(0.0~1.0)."""
    if not steps:
        return 0.0
    done = sum(1 for s in steps if s.done)
    return done / len(steps)


def overall_status(steps: list[ClosingStep]) -> str:
    """모든 단계 완료면 done, 아니면 in_progress."""
    if steps and all(s.done for s in steps):
        return STATUS_DONE
    return STATUS_IN_PROGRESS


def set_step_done(
    steps: list[ClosingStep],
    step_key: str,
    done: bool,
    *,
    now_iso: str,
) -> list[ClosingStep]:
    """지정 단계의 완료 여부를 갱신한 새 목록을 반환한다 (해당 key 없으면 원본 그대로)."""
    updated: list[ClosingStep] = []
    for s in steps:
        if s.key == step_key:
            updated.append(
                ClosingStep(
                    key=s.key,
                    label=s.label,
                    done=done,
                    done_at=now_iso if done else None,
                )
            )
        else:
            updated.append(s)
    return updated
