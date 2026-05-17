# Tax-Copilot Design — AGENT (10~15장)

본 문서는 전체 설계 문서를 4개 모듈 + 1개 인덱스로 분할한 것 중 **AGENT 모듈**입니다.
LangGraph 에이전트 그래프, HITL interrupt/resume, RAG 파이프라인, 법령 수집/버전 관리, 영수증 Vision 처리, Celery 비동기 워커를 다룹니다.
프로젝트 전체 맥락은 DESIGN_CORE.md, 도메인 모델(9장)은 DESIGN_CORE.md 참조.

Version: 5.0 (분할판)

---

## 10. LangGraph 에이전트 설계

### AgentState

상태에는 원본 이미지 bytes를 넣지 않는다. 대신 file path, receipt id, thread id, version id를 저장한다.

```python
from datetime import date
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    tenant_id: int
    receipt_id: int
    file_path: str
    file_hash: str
    attempt_number: int

    transaction_date: date | None
    law_as_of_date: date | None
    law_corpus_version: str

    image_quality: str | None
    parsed_receipt: dict | None
    retrieval_query: str | None
    relevant_laws: list[dict]
    calculation_result: dict | None
    draft_decision: dict | None
    final_decision: dict | None

    requires_human: bool
    error_message: str | None
    messages: Annotated[list, add_messages]
```

### 그래프 구조

```text
[START]
   |
   v
[image_quality_node]
   |
   +-- unreadable --> [reject_unreadable] --> [save_result] --> [END]
   |
   v
[intake_node]
   |
   v
[build_retrieval_query_node]
   |
   v
[tax_law_retrieval_node]
   |
   v
[calculation_node]
   |
   v
[audit_prepare_node]
   |
   +-- requires_human --> [human_review_node interrupt] --> [save_result] --> [END]
   |
   +-- auto_decidable --> [save_result] --> [END]
```

### 중요한 수정점

`interrupt()`가 있는 노드 앞에서 LLM 호출, DB 저장, 외부 API 호출을 하면 resume 시 다시 실행될 수 있다. 따라서 다음처럼 분리한다.

- `audit_prepare_node`: LLM 판단 초안 생성, state에 저장
- `human_review_node`: 이미 만들어진 판단 초안을 보여주고 interrupt만 수행
- `save_result_node`: resume 이후 최종 상태 저장

```python
from langgraph.types import Command, interrupt

async def audit_prepare_node(state: AgentState) -> dict:
    decision = await run_audit_llm(state)
    return {
        "draft_decision": decision.model_dump(),
        "requires_human": decision.requires_human_review,
    }

async def human_review_node(state: AgentState) -> dict:
    human_decision = interrupt({
        "type": "TAX_REVIEW_REQUIRED",
        "receipt_id": state["receipt_id"],
        "parsed_receipt": state["parsed_receipt"],
        "draft_decision": state["draft_decision"],
        "relevant_laws": state["relevant_laws"],
    })

    final_decision = {
        **state["draft_decision"],
        "human_decision": human_decision["approved"],
        "human_comment": human_decision.get("comment"),
        "requires_human_review": False,
    }
    return {"final_decision": final_decision}
```

Resume 예시는 다음처럼 `Command(resume=...)`을 사용한다.

```python
from langgraph.types import Command

await graph.ainvoke(
    Command(resume={"approved": True, "comment": "세무사 검토 후 승인"}),
    config={"configurable": {"thread_id": thread_id}},
)
```

참고: https://docs.langchain.com/oss/python/langgraph/interrupts

## 11. HITL 설계

### Checkpointer 전제

HITL은 Checkpointer 없이는 성립하지 않는다. Checkpointer는 graph state를 thread별로 저장하고, interrupt 이후 같은 `thread_id`로 재개할 수 있게 한다.

주의점:

- `.setup()`은 최초 사용 전에 직접 호출해야 한다.
- Alembic migration과 LangGraph checkpoint table setup은 별도다.
- graph를 compile한 뒤 checkpointer connection이 닫히지 않도록 lifespan에서 관리한다.
- async graph에는 `AsyncPostgresSaver`를 사용한다.

참고: https://reference.langchain.com/python/langgraph.checkpoint.postgres/PostgresSaver/setup

### FastAPI lifespan 예시

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as checkpointer:
        await checkpointer.setup()
        app.state.graph = build_graph(checkpointer=checkpointer)
        yield

app = FastAPI(lifespan=lifespan)
```

Celery worker에서도 같은 원칙을 적용한다. worker process가 살아 있는 동안 graph와 checkpointer 연결을 유지한다.

### thread_id 생성

재처리 시 같은 thread_id를 재사용하면 이전 checkpoint에서 잘못 재개될 수 있다.

```python
from uuid import uuid4

def generate_thread_id(
    tenant_id: int,
    file_hash: str,
    receipt_id: int,
    attempt_number: int,
) -> str:
    suffix = uuid4().hex[:8]
    return f"t{tenant_id}-{file_hash[:8]}-r{receipt_id}-a{attempt_number}-{suffix}"
```

### 상태 전이

```text
PENDING
  -> PROCESSING
  -> NEEDS_REVIEW
  -> APPROVED
  -> REJECTED
  -> FAILED
```

모든 상태 전이는 `audit_events`에 저장한다.

## 12. RAG 파이프라인

### 핵심 변경점

기존 설계의 `effective_date <= now`는 세무 판단에 적합하지 않다. 거래일 기준 법령을 검색해야 한다.

```python
async def search_tax_law(
    query: str,
    as_of_date: date,
    top_k: int = 10,
    rerank_top_n: int = 3,
) -> list[dict]:
    query_vector = await embed_query(query)

    results = qdrant_client.search(
        collection_name="tax_laws",
        query_vector=query_vector,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="effective_from",
                    range=DatetimeRange(lte=as_of_date),
                ),
            ],
            should=[
                FieldCondition(
                    key="effective_to",
                    range=DatetimeRange(gt=as_of_date),
                ),
                FieldCondition(
                    key="is_current",
                    match=MatchValue(value=True),
                ),
            ],
        ),
        limit=top_k,
        with_payload=True,
    )

    return rerank_or_return(results, query, rerank_top_n)
```

실제 구현에서는 `effective_to is null` 조건을 Qdrant payload 구조에 맞게 설계한다. 단순화를 위해 `is_current` 또는 큰 날짜를 둘 수 있다.

### LawChunk 스키마

```python
from datetime import date
from pydantic import BaseModel

class LawChunk(BaseModel):
    chunk_id: str
    law_id: str
    law_mst: str | None = None
    law_name: str
    article_no: str | None
    paragraph_no: str | None = None
    subparagraph_no: str | None = None
    content: str
    effective_from: date
    effective_to: date | None = None
    promulgation_date: date | None = None
    source_url: str | None = None
    references: list[str] = []
    content_hash: str
    corpus_version: str
```

`chunk_id`는 법령명과 조문 번호만으로 만들지 않는다. 시행일 또는 corpus version을 포함한다.

예:

```text
vat-20240101-art39-p1-sub4-7f3a9c
```

### Embedding 전략

2026년 기준 Gemini embedding은 `gemini-embedding-2`를 기본 모델로 사용한다.

- `gemini-embedding-2`: stable, multimodal capable, 8192 input token limit, 128~3072 output dimensions
- `gemini-embedding-001`: stable, text-only, 2048 input token limit, fallback 후보

`gemini-embedding-2`는 `task_type` 필드를 사용하지 않는다. 검색용 쿼리는 `task: search result | query: {content}`, 문서는 `title: {title} | text: {content}` 형태의 prefix를 붙여 일관되게 임베딩한다.

`gemini-embedding-2`는 768/1536 같은 비기본 차원도 자동 정규화한다. `gemini-embedding-001`을 fallback으로 사용할 때만 3072가 아닌 차원에 대해 수동 normalize가 필요하다.

두 모델의 embedding space는 호환되지 않는다. 모델을 바꾸면 전체 corpus를 재임베딩해야 한다.

Qdrant collection 생성 시 dimension을 명시한다.

```python
EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIM = 768

client.create_collection(
    collection_name="tax_laws",
    vectors_config=VectorParams(
        size=EMBEDDING_DIM,
        distance=Distance.COSINE,
    ),
    hnsw_config=HnswConfigDiff(
        m=16,
        ef_construct=100,
    ),
)
```

### Reranker 전략

FlashRank는 비용이 낮고 로컬 CPU 실행이 가능하다는 장점이 있다. 다만 기본 MS MARCO 계열 모델은 영어 retrieval 데이터셋 기반이므로 한국어 세법에 바로 적합하다고 단정하지 않는다.

MVP 순서:

1. Qdrant dense retrieval만으로 top-k 정확도 측정
2. FlashRank 적용 전후 비교
3. 한국어 또는 다국어 reranker 후보 비교
4. README에는 실측 결과만 표기

### PostgreSQL fallback

PostgreSQL 기본 full-text search에 `korean` configuration이 있다고 가정하지 않는다.

MVP fallback 후보:

- `ILIKE` 기반 단순 검색
- `pg_trgm` similarity
- `simple` text search
- 후순위로 PGroonga 검토

## 13. 법령 수집과 버전 관리

### 데이터 소스

| 소스 | MVP 사용 | 비고 |
| --- | --- | --- |
| law.go.kr API | 사용 | 공식 법령 원문 |
| taxlaw.nts.go.kr | 제한적 사용 | 예규/질의회신 수동 선별 |
| data.go.kr | 후순위 | KPI 또는 통계 대시보드용 |
| 국회 의안정보시스템 | 후순위 | 개정 취지 RAG |

law.go.kr API는 `lawSearch.do`로 목록을 가져오고, `lawService.do`로 본문을 가져오는 흐름을 사용한다.

참고: https://open.law.go.kr/LSO/openApi/guideResult.do

### 버전 관리 원칙

법령 업데이트 시 기존 chunk를 무조건 덮어쓰지 않는다.

저장해야 하는 것:

- 법령 ID
- MST 또는 법령일련번호
- 공포일자
- 시행일자
- 조문 번호
- 원문 content hash
- 수집 시각
- corpus version

이유:

- 과거 영수증 판단을 재현해야 한다.
- 법령 개정 전후 판단 결과가 달라질 수 있다.
- README와 테스트에서 특정 corpus version 기준 결과를 고정해야 한다.

### 수집 스크립트 순서

```text
scripts/
  01_collect_laws.py
  02_normalize_law_versions.py
  03_chunk_laws.py
  04_embed_chunks.py
  05_upload_to_qdrant.py
  06_seed_sample_precedents.py
  07_evaluate_rag.py
```

MVP에서는 1번부터 5번까지를 작은 데이터셋으로만 구현한다.

## 14. 영수증 파일 처리와 Vision 파이프라인

### 파일 검증

`UploadFile.content_type`만 믿지 않는다.

필수 검증:

- size limit
- magic bytes 검사
- 허용 확장자
- 이미지 decode 가능 여부
- PDF page limit
- malware scan은 후순위
- EXIF metadata 제거는 가능하면 초기에 적용

```python
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
```

### Storage 경로

전체 서비스 기준 `file_hash unique`는 위험하다. tenant별로 분리한다.

```text
receipts/{tenant_id}/{yyyy}/{mm}/{hash_prefix}/{file_hash}.{ext}
```

DB unique constraint:

```text
unique(tenant_id, file_hash)
```

### Vision 처리

MVP 단계:

1. OpenCV 또는 Pillow로 이미지 decode 가능 여부 확인
2. blur, brightness, size 등 deterministic quality check
3. Gemini Vision으로 필드 추출
4. Pydantic structured output 검증
5. 실패 시 HITL 또는 재업로드 요청

Gemini 호출을 품질 분류에 한 번, OCR에 한 번 쓰면 비용과 latency가 늘어난다. MVP에서는 deterministic quality check를 먼저 적용하고, 필요한 경우에만 Gemini를 호출한다.

## 15. 비동기 처리와 Celery

### Celery를 쓰는 이유

FastAPI BackgroundTasks는 프로세스 재시작 시 작업 유실 리스크가 있다. AI 처리처럼 30초 이상 걸리는 작업은 Celery로 분리한다.

### Idempotency

Celery는 worker crash 시 같은 task가 다시 실행될 수 있다. `acks_late=True`를 쓰려면 task가 idempotent해야 한다.

참고: https://docs.celeryq.dev/en/stable/userguide/tasks.html

### Redis lock

```python
def dispatch_receipt_task(
    tenant_id: int,
    receipt_id: int,
    file_path: str,
    file_hash: str,
) -> str:
    lock_key = f"lock:receipt:{tenant_id}:{file_hash}"

    if not redis_client.set(lock_key, "1", nx=True, ex=300):
        raise DuplicateReceiptError("이미 처리 중인 영수증입니다.")

    task_id = f"receipt-{tenant_id}-{file_hash}"
    task = process_receipt_task.apply_async(
        kwargs={
            "tenant_id": tenant_id,
            "receipt_id": receipt_id,
            "file_path": file_path,
            "file_hash": file_hash,
        },
        task_id=task_id,
    )
    return task.id
```

### Celery 상태와 DB 상태 분리

Celery result backend의 상태만 믿지 않는다. 사용자 화면에는 DB의 `receipts.status`를 보여준다.


---

## 관련 문서

- **DESIGN_INDEX.md** — 전체 프로젝트 1~200줄 요약 (이것부터 읽기)
- **DESIGN_CORE.md** — 개요, 원칙, 법적 포지셔닝, MVP, 기술 결정, 스택, 아키텍처, 폴더 구조, 도메인 모델 (1~9장)
- **DESIGN_AGENT.md** — LangGraph, HITL, RAG, 법령 수집, Vision, Celery (10~15장)
- **DESIGN_OPS.md** — DB, 인증, 관측, Graceful Degradation, 테스트, 배포 (16~21장)
- **DESIGN_PLAN.md** — 개발 로드맵, 일정, 백로그, 함정, 시연 자료, README, 부록 (22~29장)
