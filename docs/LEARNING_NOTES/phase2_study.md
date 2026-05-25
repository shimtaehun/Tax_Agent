# Phase 2 학습 노트 — LangGraph 워크플로우 & HITL

> LangGraph는 이 프로젝트에서 가장 중요한 기술입니다.
> 코드를 열어서 직접 실행 흐름을 추적하면서 읽으세요.

---

## 1. LangGraph가 무엇인가?

### 기존 AI 파이프라인의 문제

LLM을 단순히 호출하면:
```python
response = llm.invoke("이 영수증 분석해줘")
```

- 중간에 실패하면 처음부터 다시 해야 합니다
- "이 단계는 사람이 검토해야 해"라고 멈추기 어렵습니다
- 어떤 단계까지 완료됐는지 추적이 안 됩니다

### LangGraph의 해결 방법

AI 처리를 **그래프(노드 + 엣지)**로 표현합니다:

```
[image_quality] → [intake] → [retrieval] → [calculation] → [audit_prepare]
                                                                    ↓
                                                            (사람 검토 필요?)
                                                            ↓Yes        ↓No
                                                    [human_review]  [save_result]
                                                            ↓
                                                    [save_result]
```

각 노드의 결과가 **state**에 쌓입니다. 그래프가 중간에 멈춰도(interrupt), state가 checkpoint에 저장되어 있어서 나중에 이어서 실행할 수 있습니다.

---

## 2. AgentState — 상태 설계 원칙

```python
# src/tax_copilot/agents/state.py
class AgentState(TypedDict):
    tenant_id: int
    receipt_id: int
    file_path: str          # ← 이미지 bytes가 아닌 파일 경로만!
    file_hash: str

    image_quality: str | None
    parsed_receipt: dict | None
    relevant_laws: list[dict]
    calculation_result: dict | None
    draft_decision: dict | None
    final_decision: dict | None

    requires_human: bool
    messages: Annotated[list, add_messages]
```

### 핵심 원칙: 이미지 bytes를 state에 넣지 않는다

왜냐하면:
1. **직렬화 문제**: LangGraph는 state를 JSON으로 직렬화해서 checkpoint에 저장합니다. bytes를 JSON에 넣으면 용량이 커지고 에러가 납니다.
2. **메모리 문제**: 10MB 이미지 × 동시 100개 처리 = 1GB+ 메모리
3. **재개 시 문제**: checkpoint에서 state를 복원할 때 bytes를 다시 로드하면 느립니다

대신 `file_path`를 저장하고, 이미지가 필요할 때 디스크에서 읽습니다.

### add_messages reducer

```python
messages: Annotated[list, add_messages]
```

일반 TypedDict 필드는 덮어씁니다 (`state["x"] = new_value`). `add_messages` reducer가 붙은 필드는 새 메시지를 **기존 목록에 추가**합니다. 여러 노드에서 메시지를 추가해도 유실되지 않습니다.

---

## 3. 그래프 구성 — 노드와 엣지

```python
# src/tax_copilot/agents/graph.py
def build_graph(checkpointer: BaseCheckpointSaver) -> StateGraph:
    builder = StateGraph(AgentState)

    # 노드 등록
    builder.add_node("image_quality", image_quality_node)
    builder.add_node("human_review", human_review_node)
    # ...

    # 엣지 연결
    builder.add_edge(START, "image_quality")
    builder.add_conditional_edges("image_quality", _route_after_quality)
    builder.add_conditional_edges("audit_prepare", _route_after_audit)

    return builder.compile(checkpointer=checkpointer)
```

### conditional_edges — 조건 분기

```python
def _route_after_quality(state: AgentState) -> str:
    return "reject_unreadable" if state.get("image_quality") == "unreadable" else "intake"
```

이 함수가 다음에 실행할 노드 이름을 반환합니다. `if/else`로 처리 경로를 나눕니다.

### checkpointer란?

그래프 실행 중간의 state를 저장하는 저장소입니다.
- `MemorySaver`: 메모리에만 저장 (테스트용)
- `AsyncPostgresSaver`: PostgreSQL에 저장 (프로덕션용) — interrupt 후 서버가 재시작해도 재개 가능

---

## 4. HITL 패턴 — 가장 중요한 설계

HITL = Human In The Loop. AI가 판단하다가 불확실하면 사람(세무사)에게 검토를 넘기는 패턴.

### 잘못된 설계 (하면 안 됨)

```python
async def audit_prepare_node(state):
    draft = llm.invoke(...)           # LLM으로 판단
    interrupt({"draft": draft})       # ← 여기서 interrupt 호출
    # ... resume 후 코드
```

**문제**: resume할 때 `interrupt()` 이전 코드가 다시 실행됩니다. LLM을 두 번 호출하게 됩니다. 결과가 다를 수 있고, 비용이 이중으로 발생합니다.

### 올바른 설계 (이 프로젝트의 방식)

```python
# audit_prepare_node: LLM 작업만, interrupt 없음
async def audit_prepare_node(state: AgentState) -> dict:
    draft = ...   # 판단 초안 생성
    return {
        "draft_decision": draft,
        "requires_human": True,   # interrupt 필요 여부만 설정
    }

# human_review_node: interrupt만, LLM/DB/API 없음
async def human_review_node(state: AgentState) -> dict:
    human_decision: dict = interrupt({
        "type": "TAX_REVIEW_REQUIRED",
        "receipt_id": state["receipt_id"],
        "draft_decision": state.get("draft_decision"),
    })
    # interrupt() 이후 코드: resume 시 실행됨
    return {"final_decision": {**state["draft_decision"], ...human_decision}}
```

**원칙**: 비싸거나 부작용 있는 작업(LLM, DB 저장)을 interrupt 전에 다 끝냅니다. interrupt 후에는 사람의 결정만 받습니다.

---

## 5. interrupt() — 실행 일시 중단

### LangGraph 1.2.x에서 interrupt()가 하는 일

```python
# 잘못된 예상 (1.2.x 이전 방식)
try:
    result = await graph.ainvoke(state, config=config)
except GraphInterrupt as e:   # ← 이렇게 예외로 잡는 게 아님!
    ...

# 올바른 방식 (1.2.x)
result = await graph.ainvoke(state, config=config)
if "__interrupt__" in result:
    # 그래프가 일시 중단됨
    interrupt_value = result["__interrupt__"][0].value
```

`interrupt()`는 예외를 발생시키지 않습니다. 대신:
1. 현재 state를 checkpoint에 저장합니다
2. 그래프가 반환됩니다 (정상 종료처럼 보임)
3. 반환값에 `__interrupt__` 키가 포함됩니다

### resume 방법

```python
from langgraph.types import Command

# 세무사가 결정을 내린 후
final_state = await graph.ainvoke(
    Command(resume={"approved": True, "comment": "검토 완료"}),
    config={"configurable": {"thread_id": same_thread_id}},  # 같은 thread_id 필수!
)
```

`thread_id`가 같아야 이전 checkpoint를 찾을 수 있습니다. 다른 `thread_id`를 쓰면 처음부터 다시 시작합니다.

---

## 6. thread_id — 실행 추적

```python
# src/tax_copilot/agents/graph.py:72-78
def generate_thread_id(tenant_id, file_hash, receipt_id, attempt_number) -> str:
    suffix = uuid4().hex[:8]  # 매번 랜덤
    return f"t{tenant_id}-{file_hash[:8]}-r{receipt_id}-a{attempt_number}-{suffix}"
```

예시: `t1-a1b2c3d4-r42-a1-f7e8d9c0`

### 왜 UUID suffix를 붙이는가?

같은 영수증을 재처리하면 `tenant_id`, `file_hash`, `receipt_id`, `attempt_number`가 모두 같습니다. `thread_id`도 같으면 이전 checkpoint에서 잘못된 상태로 재개될 수 있습니다. UUID suffix로 매번 새로운 실행을 보장합니다.

---

## 7. 결정론적 계산 도구 — LLM이 금액을 계산하면 안 되는 이유

### 문제

LLM은 확률적입니다. 같은 입력에도 다른 답이 나올 수 있습니다. 세금 계산에서 "10000원의 10%는 1000원"이 "1001원"으로 나오면 안 됩니다.

또한 LLM은 부동소수점 오류를 일으킵니다:
```python
>>> 0.1 + 0.2
0.30000000000000004   # ← 이런 오류가 세금 계산에 있으면 안 됨
```

### 해결: Python Decimal

```python
# src/tax_copilot/agents/tools/vat.py
from decimal import ROUND_DOWN, Decimal

def calculate_vat_from_supply_value(supply_value_krw: int, ...) -> dict[str, int]:
    rate = Decimal(tax_rate_basis_points) / Decimal(10000)
    vat = (Decimal(supply_value_krw) * rate).quantize(Decimal("1"), rounding=ROUND_DOWN)
    return {"vat_krw": int(vat), ...}
```

- 입력: 정수 (원 단위)
- 계산: `Decimal` (정밀한 소수점 연산)
- 출력: 정수 (원 단위, 소수점 이하 내림)
- LLM은 이 함수를 "도구(tool)"로 호출합니다. 금액 계산을 직접 하지 않습니다.

### basis_points란?

세율을 정수로 표현하는 방법입니다. `1000 basis points = 10.00%`. 이렇게 하면 세율도 정수로 처리할 수 있어서 부동소수점 오류를 피합니다.

---

## 8. 각 노드 역할 정리

| 노드 | 파일 | 현재 구현 | Phase 4 교체 대상 |
|------|------|-----------|-----------------|
| `image_quality` | `nodes/image_quality.py` | 파일 크기 기준 (1KB 미만 = unreadable) | Gemini Vision |
| `intake` | `nodes/intake.py` | Mock (confidence=0.95 반환) | Gemini 구조화 출력 |
| `build_retrieval_query` | `nodes/retrieval.py` | Mock | Gemini 쿼리 생성 |
| `tax_law_retrieval` | `nodes/retrieval.py` | Mock (빈 목록 반환) | Qdrant 벡터 검색 |
| `calculation` | `nodes/calculation.py` | `calculate_vat_from_supply_value` 호출 | 동일 (이미 완성) |
| `audit_prepare` | `nodes/audit_prepare.py` | Rule-based 판단 초안 | Gemini 판단 |
| `human_review` | `nodes/human_review.py` | `interrupt()` 호출 | 동일 (이미 완성) |
| `save_result` | `nodes/save_result.py` | State 완료 표시 | Celery task 연동 |

---

## 9. 처리 경로 3가지

### 경로 A: 자동 처리 (laws 있음 + confidence 높음)
```
START → image_quality(ok) → intake → retrieval → calculation → audit_prepare
→ save_result → END
```
`final_decision["human_approved"] = None` (자동 처리됨)

### 경로 B: HITL (laws 없음 또는 confidence 낮음)
```
START → image_quality(ok) → ... → audit_prepare → human_review[interrupt]
→ (세무사 결정 대기)
→ [resume] → save_result → END
```
`final_decision["human_approved"] = True/False`

### 경로 C: 판독 불가 이미지
```
START → image_quality(unreadable) → reject_unreadable → save_result → END
```
`final_decision["evidence_status"] = "unreadable"`

현재(Phase 2)에서는 retrieval이 빈 목록을 반환하므로 모든 영수증이 경로 B로 갑니다.

---

## 10. HITL이 필요한 조건 (audit_prepare 로직)

```python
# src/tax_copilot/agents/nodes/audit_prepare.py:19-36
def _should_require_human(state: AgentState) -> tuple[bool, str | None]:
    # 조건 1: 법령 근거 없음
    if not state.get("relevant_laws"):
        return True, "검색된 법령 근거가 없습니다."

    # 조건 2: 추출 신뢰도 낮음 (75% 미만)
    confidence = parsed.get("extraction_confidence", 0.0)
    if confidence < 0.75:
        return True, f"추출 신뢰도가 낮습니다: {confidence:.2f}"

    # 조건 3: 계산 실패
    if state.get("calculation_result") is None and ...:
        return True, "세액 계산에 실패했습니다."

    return False, None
```

Phase 3에서 실제 법령 검색이 구현되면, `relevant_laws`가 채워져서 경로 A로 자동 처리가 가능해집니다.

---

## 핵심 질문 목록 (면접 준비)

1. "LangGraph에서 state란 무엇이고, 왜 bytes를 state에 넣으면 안 되나요?"
2. "HITL 패턴에서 interrupt를 human_review_node에서만 호출하는 이유는?"
3. "LangGraph 1.2.x에서 interrupt()의 동작이 어떻게 바뀌었나요?"
4. "thread_id에 UUID suffix를 붙이는 이유는?"
5. "LLM이 금액 계산을 하면 안 되는 이유는? Decimal을 쓰는 이유는?"
6. "checkpointer가 없으면 interrupt/resume이 왜 불가능한가요?"
7. "이 시스템에서 영수증 처리 경로는 몇 가지이고 각각 어떤 조건인가요?"
