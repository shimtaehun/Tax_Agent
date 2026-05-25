# Phase 2 완료 보고서 — LangGraph 워크플로우

완료일: 2026-05-24

## 목표

LangGraph 기반 세무 처리 워크플로우를 구현하고 HITL(인간 검토 개입) 패턴을 정확히 검증한다.
DB 없이 MemorySaver로 전체 흐름을 테스트하여 Phase 3(실 LLM/RAG) 통합 전에 골격을 확정한다.

---

## 구현한 컴포넌트

### AgentState (`src/tax_copilot/agents/state.py`)
- `TypedDict` 기반, 모든 값 JSON-serializable
- 이미지 bytes 절대 저장 금지 — 파일 경로와 hash만 저장
- `messages` 필드: `add_messages` reducer로 LangGraph 메시지 누적

### 처리 노드 6개
| 노드 | 파일 | 역할 |
|---|---|---|
| `image_quality_node` | `nodes/image_quality.py` | 파일 크기 기반 품질 판정 (Phase 4: Gemini Vision으로 교체) |
| `intake_node` | `nodes/intake.py` | 영수증 파싱 Mock (Phase 4: Gemini 구조화 출력으로 교체) |
| `retrieval_node` | `nodes/retrieval.py` | 법령 검색 Mock — 빈 목록 반환 (Phase 3: Qdrant RAG으로 교체) |
| `calculation_node` | `nodes/calculation.py` | `calculate_vat_from_supply_value` 호출, LLM이 금액 계산 안 함 |
| `audit_prepare_node` | `nodes/audit_prepare.py` | 판단 초안 생성, HITL 여부 결정 — **`interrupt()` 호출 안 함** |
| `human_review_node` | `nodes/human_review.py` | **`interrupt()` 유일 호출 지점** — LLM/DB/API 없음 |
| `save_result_node` | `nodes/save_result.py` | resume 후 final_decision 저장, `reject_unreadable_node` 포함 |

### 결정론적 계산 도구 (`src/tax_copilot/agents/tools/vat.py`)
- `calculate_vat_from_supply_value(supply_value_krw, ...)` — Python `Decimal`, ROUND_DOWN
- `calculate_entertainment_limit(total_expense_krw, revenue_krw)` — 법인세법 제25조

### 그래프 (`src/tax_copilot/agents/graph.py`)
- `build_graph(checkpointer) -> StateGraph`
- `generate_thread_id(tenant_id, file_hash, receipt_id, attempt_number) -> str`
  - 형식: `t{tid}-{hash8}-r{rid}-a{att}-{uuid8}` (uuid suffix로 재시도마다 고유)
- 조건 엣지 2개: `_route_after_quality`, `_route_after_audit`

---

## HITL 패턴 — 핵심 설계 결정

```
audit_prepare_node   → 판단 초안 생성, requires_human 설정 (interrupt 없음)
    ↓ (requires_human=True)
human_review_node    → interrupt() 호출만, 결과를 state에 저장 안 함
    ↓ (Command(resume=...))
save_result_node     → resume 데이터 + draft_decision 합쳐 final_decision 구성
```

이유: `audit_prepare_node`에서 interrupt하면 resume 시 LLM이 재실행되어 비용 이중 발생 + 비결정성.
`human_review_node`는 순수 신호 역할만 한다.

---

## LangGraph 1.2.x interrupt 동작 변경점 (중요)

Phase 2 개발 중 발견한 breaking change:

| 항목 | 이전 예상 | 실제 동작 |
|---|---|---|
| interrupt 발동 시 | `GraphInterrupt` 예외 발생 | 예외 없음, graph 일시 중단 |
| 반환 값 | (없음, 예외로 탈출) | `{"__interrupt__": [Interrupt(value=...)], ...}` |
| resume 방법 | 동일 (Command 사용) | 동일 — `Command(resume=...) + 같은 thread_id config` |

테스트 패턴도 이에 맞게 수정했다:
```python
# 올바른 패턴 (LangGraph 1.2.x)
result = await graph.ainvoke(state, config=config)
assert "__interrupt__" in result
assert result["__interrupt__"][0].value["type"] == "TAX_REVIEW_REQUIRED"

final = await graph.ainvoke(Command(resume={...}), config=config)
assert "__interrupt__" not in final
```

---

## 테스트 결과

`tests/test_graph.py` — 12개 전체 통과:

| 클래스 | 테스트 수 | 내용 |
|---|---|---|
| `TestGraphCompile` | 1 | 컴파일 오류 없음 |
| `TestAutoDecisionPath` | 1 | 자동 경로 실행 완주 |
| `TestHITLPath` | 2 | interrupt 발동 + 승인/반려 resume |
| `TestUnreadablePath` | 1 | 1KB 미만 파일 → reject_unreadable 경유 |
| `TestTools` | 7 | VAT 계산, 접대비 한도, thread_id 형식/유일성 |

전체 테스트 스위트 38개 통과 (test_auth 11, test_graph 12, test_healthz 1, test_validation 14).

---

## Phase 3 예고

- `retrieval_node` 교체: Qdrant + Gemini embedding, transaction_date 기준 법령 검색
- `law_corpus_version` 활용: 날짜별 법령 버전 관리
- RAG 스키마: `LawChunk(chunk_id, law_name, effective_from, effective_to, text, ...)`
- `relevant_laws`가 채워지면 `audit_prepare_node`의 `requires_human=False` 경로가 활성화됨
