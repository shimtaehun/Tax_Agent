# Tax-Copilot Design — PLAN (22~29장)

본 문서는 전체 설계 문서를 4개 모듈 + 1개 인덱스로 분할한 것 중 **PLAN 모듈**입니다.
5주 개발 로드맵 (Phase 0~6), 후순위 백로그, 제거/축소 결정, 알려진 함정, 포트폴리오 시연 자료, README 템플릿, 공식 문서 링크 부록을 다룹니다.
구현 상세는 CORE/AGENT/OPS 참조.

Version: 5.1 (분할판)

---

## 22. 개발 로드맵

각 Phase는 학습 목표, 핵심 키워드, 산출물을 포함한다.

진행 원칙: 외부 AI, Qdrant, R2, Celery를 한 번에 붙이지 않는다. 먼저 mock 기반으로 영수증 업로드 → 판단 후보 생성 → HITL 검토 → 감사 로그 저장까지 수직 슬라이스를 완성하고, 그 뒤 외부 연동을 하나씩 교체한다.

### Phase 0. Repository and Skeleton

학습 목표: Python 프로젝트 구조와 의존성 관리의 현업 표준을 이해한다.

핵심 키워드: src layout, pip-tools, Docker Compose, pydantic-settings, structlog, Alembic

작업:

- FastAPI skeleton
- Next.js skeleton (Week 5까지는 빈 폴더만)
- Docker Compose for PostgreSQL and Redis
- Settings management
- Alembic setup
- structlog 설정
- basic CI

산출물:

- 빈 폴더 트리와 lint/format 통과
- `docker-compose up`만으로 dev 환경 기동
- `/healthz` endpoint 응답

### Phase 1. Core Backend

학습 목표: 멀티테넌시 인증과 파일 업로드의 안전한 구현을 익힌다.

핵심 키워드: JWT, tenant scope, magic bytes, storage abstraction, audit event

작업:

- tenant/user/receipt models
- JWT auth
- file upload validation
- local storage first
- R2 abstraction only after local upload is stable
- audit events
- admin pending API

산출물:

- 로그인 → 영수증 업로드 → DB 저장 까지 동작
- audit_events 테이블에 모든 상태 전이 기록

### Phase 2. Minimal AI Workflow

학습 목표: LangGraph의 상태 기반 워크플로우와 HITL interrupt/resume 패턴을 이해한다.

핵심 키워드: AgentState, Checkpointer, interrupt, Command(resume=...), idempotency

작업:

- LangGraph state
- mocked intake node
- mocked law retrieval node
- deterministic calculation tool
- audit prepare node
- HITL interrupt/resume
- result save

목표: 외부 AI 없이도 전체 workflow가 테스트에서 통과한다.

산출물:

- LangGraph graph compile 성공
- HITL interrupt 발동 후 resume 성공
- 전체 흐름 integration test 통과

### Phase 3. RAG Corpus MVP

학습 목표: 시점 기반 RAG 검색과 chunk version 관리를 익힌다.

핵심 키워드: law.go.kr API, chunking, embedding, Qdrant filter, corpus version

작업:

- law.go.kr small collection
- chunk schema
- embedding
- Qdrant upload
- transaction date based retrieval
- citation 저장

산출물:

- 20개 내외 법령 chunk가 sample corpus에 저장됨
- as_of_date를 바꾸면 다른 결과가 나오는 검색 확인
- LangGraph에서 RAG 노드가 실제 chunk 반환
- Qdrant adapter는 in-memory 검색 계약이 고정된 뒤 교체

### Phase 4. Vision Integration

학습 목표: Gemini Vision의 structured output과 Pydantic 검증 패턴을 익힌다.

핵심 키워드: Gemini Vision, structured output, deterministic quality check, fallback to HITL

작업:

- Gemini Vision structured extraction
- image quality check
- Pydantic validation
- extraction failure HITL

산출물:

- 실제 영수증 이미지에서 ParsedReceipt 생성
- 흐릿한 이미지는 HITL로 자동 이관

### Phase 5. Celery Integration

학습 목표: 비동기 작업 큐와 idempotency 보장 기법을 익힌다.

핵심 키워드: Celery, acks_late, Redis lock, task_id, idempotent DB update

작업:

- receipt task dispatch
- idempotent lock
- retry
- timeout
- DB status polling

산출물:

- 영수증 업로드 → Celery 처리 → 사용자가 polling으로 상태 확인까지 동작
- Celery worker 강제 종료 후 재시작해도 중복 처리 없음

### Phase 6. Portfolio Polish

학습 목표: 면접에서 통하는 포트폴리오를 만든다.

핵심 키워드: README, ADR, demo, architecture diagram, talking points

작업:

- Next.js로 최소 UI 구현 (로그인, 업로드, admin 검토)
- Render/Railway 배포
- README 완성
- architecture diagram (light/dark)
- demo GIF or video
- ADR 정리
- LEARNING_NOTES 정리
- 면접 talking points 매핑

## 23. 5주 일정과 Phase 0 분해

### 23.1. 5주 마일스톤

기간: 2026-05-24 (일) ~ 2026-06-27 (토)
가용 시간: 평일 2h × 5 + 주말 10h × 2 = 주 30h, 총 150h

| 주차 | Phase | 주요 산출물 |
| --- | --- | --- |
| Week 1 | Phase 0 + Phase 1 전반 | repo skeleton, Docker Compose, Alembic, seed admin/default client, local upload |
| Week 2 | Phase 1 후반 + Phase 2 | Receipt upload, mock Vision/RAG, LangGraph state, HITL, audit log |
| Week 3 | Phase 3 | sample law corpus, Gemini embedding, 거래일 검색, Qdrant adapter |
| Week 4 | Phase 4 + Phase 5 | Gemini Vision, Celery, Redis lock, idempotency |
| Week 5 | Phase 6 + 배포 | Next.js, Railway 배포, README, demo |

이 일정은 2026-05-24 재기획 기준의 목표 페이스다. 매주 일요일에 실제 진척을 보고 R2, Qdrant, Celery, UI 범위를 줄일지 결정한다.

### 23.2. Phase 0 step 분해 (Week 1, 약 18h)

| Step | 내용 | 예상 | 학습 주제 |
| --- | --- | --- | --- |
| 0.1 | Repo 초기화, 폴더 구조, .gitignore | 1.5h | src layout, core/infra 분리 이유 |
| 0.2 | requirements/ + pip-tools | 2h | .in vs .txt, hash pinning, 환경 분리 |
| 0.3 | pyproject.toml + ruff + mypy + pre-commit | 2h | ruff 규칙셋, mypy strict 범위, pre-commit hooks |
| 0.4 | Docker Compose (Postgres + Redis) | 2h | volumes, networks, healthcheck |
| 0.5 | FastAPI skeleton + pydantic-settings | 3h | lifespan, DI, BaseSettings, /healthz |
| 0.6 | SQLAlchemy 2.0 async + Alembic | 3h | AsyncSession, env.py async 패턴 |
| 0.7 | structlog 구조화 로깅 | 1.5h | JSON 로깅, request_id contextvar, PII masking |
| 0.8 | GitHub Actions CI | 2h | workflows, services, cache |
| 0.9 | ADR + Phase 0 학습 노트 회고 | 1h | Michael Nygard ADR 템플릿 |

각 step 완료 시 별도 PR로 머지한다 (혼자 작업이지만 PR 단위 연습).

## 24. 후순위 기능 백로그

이 섹션은 "빼는 것"이 아니라 "나중에 붙일 위치를 정해두는 것"이다.

### A. RAG 품질 고도화

- RAGAS 평가
- 한국어 reranker 비교
- hybrid search
- query rewriting
- 법령 개정 이력 diff UI
- 예규/질의회신 대량 수집

### B. 운영 안정성

- circuit breaker
- dead letter queue
- admin retry button
- alerting
- service health check dashboard
- Celery Flower 또는 대체 모니터링
- OpenTelemetry 분산 trace

### C. 비용 최적화

- Semantic Cache
- prompt cache
- batch embedding
- model routing
- LLM call budget per tenant

### D. 실시간 UX

- SSE 알림
- WebSocket 알림
- review assignment
- admin notification

### E. 보안 고도화

- malware scan
- object lifecycle retention
- field-level encryption
- audit log export
- tenant-level data deletion
- Redis 기반 sliding window rate limiter

### F. 비즈니스 대시보드

- AI 자동 처리율
- HITL 이관율
- AI 판단 번복률
- 평균 처리 시간
- receipt당 평균 비용
- 고객사별 리스크 분포

### G. 외부 연동

- 회계 프로그램 export
- CSV/Excel export
- Slack notification
- 국세청 홈택스 연계는 포트폴리오에서는 문서상 future work로만 둔다.

## 25. 제거 또는 축소할 항목

### 당장 제거

- README에 실측 전 KPI 숫자 기재
- README에 실측 전 RAGAS 숫자 기재
- LLM float 계산 예제
- `effective_date <= now` 법령 검색
- 전체 서비스 기준 `file_hash unique`
- Redis `KEYS` 기반 semantic cache
- `to_tsvector('korean', ...)` 가정

### MVP에서 축소

- Image Quality Classifier의 Gemini 호출은 OpenCV deterministic check로 축소
- Unstructured API는 영수증 이미지 MVP에서 제외
- 법령 자동 업데이트는 수동 script로 먼저 검증
- FlashRank는 성능 비교 후 채택
- KPI 대시보드는 API와 데이터가 쌓인 뒤 구현

## 26. 알려진 함정과 해결책

| 구분 | 문제 | 해결책 |
| --- | --- | --- |
| 법령 버전 | 오늘 법령으로 과거 거래 판단 | 거래일 기준 `effective_from/effective_to` 필터 |
| 재현성 | chunk upsert로 과거 근거 사라짐 | corpus version과 versioned chunk id 저장 |
| HITL | interrupt 전 LLM 호출이 resume 때 재실행 | prepare node와 interrupt node 분리 |
| Checkpointer | graph 반환 후 connection close | app/worker lifespan에서 유지 |
| 계산 | float 오차 | Decimal 또는 integer basis points |
| 멀티테넌시 | 같은 파일 hash가 전체 사용자 중복 처리 | `(tenant_id, file_hash)` unique |
| RAG | 영어 reranker를 한국어에 무검증 적용 | 한국어 데이터로 성능 비교 후 채택 |
| FTS | PostgreSQL `korean` config 가정 | `simple`, `pg_trgm`, PGroonga 검토 |
| Cache | Redis KEYS 전체 scan | MVP 제외 또는 vector index 기반 cache |
| 비용 | free tier 변경 | 기준일과 사용량 계측 명시 |
| DB JSON | 내부 값 변경 미감지 | dict 전체 재할당 |
| Celery | 중복 실행 | idempotent DB update와 Redis lock |
| R2 | content-type spoofing | magic bytes 검사 |
| 적격증빙 | 모든 영수증을 동일 취급 | evidence_type 필드로 분류 |
| 법적 책임 | AI 판단을 최종 결론으로 표시 | 면책 문구 + HITL 강제 |
| 로그 | PII 평문 노출 | structlog processor에서 자동 마스킹 |

## 27. 포트폴리오 마감과 시연 자료

### 27.1. README 우선순위

면접관이 30초 안에 흥미를 잃지 않도록 다음 순서로 README 상단을 구성한다.

1. 한 줄 소개와 슬로건
2. demo GIF (15초 내외)
3. architecture diagram (light/dark)
4. Key Engineering Decisions 4~5개 (왜 그렇게 만들었는지)
5. 기술 스택
6. Local Development
7. Roadmap

### 27.2. demo GIF

- 길이: 15~20초
- 내용: 영수증 업로드 → AI 분석 진행 → HITL 검토 화면 → 승인 → 결과
- 도구: macOS Kap, ScreenToGif, peek

배경 음악과 자막은 넣지 않는다. UI 동작만으로 흐름이 보여야 한다.

### 27.3. 아키텍처 다이어그램

- light mode와 dark mode 두 버전을 SVG로 export
- 구성요소 박스 색은 카테고리별로 통일 (외부 서비스 한 색, 내부 서비스 한 색)
- 화살표 방향은 데이터 흐름 또는 호출 방향 중 하나로 통일

### 27.4. ADR 우선순위

다음 ADR을 최소한 작성한다.

- 0001 - Why LangGraph
- 0002 - Why transaction-date-based law retrieval
- 0003 - Why PostgreSQL Checkpointer (not Redis or SQLite)
- 0004 - Why hexagonal architecture (core/infra separation)
- 0005 - Why pip + pip-tools (not uv or Poetry)

각 ADR은 Michael Nygard 템플릿(Context, Decision, Consequences)을 따른다.

### 27.5. 면접 talking points 매핑

다음 질문에 대한 답변을 미리 만들어둔다.

- "이 프로젝트에서 가장 어려웠던 기술 결정은?"
- "왜 LangGraph를 선택했나요?"
- "거래일 기준 법령 검색은 어떻게 구현했나요?"
- "AI가 잘못된 판단을 내릴 가능성은 어떻게 다루나요?"
- "비용은 얼마나 들었나요?"
- "이 시스템의 한계는 무엇인가요?"
- "혼자 만들면서 가장 많이 배운 부분은?"

각 답변은 LEARNING_NOTES에 미리 정리하고, 핵심 키워드만 외운다.

### 27.6. 블로그 글 (선택)

여건이 되면 다음 주제 중 1~2개를 기술 블로그로 작성한다.

- LangGraph HITL의 prepare/interrupt 분리 패턴
- 세무 도메인에서 시점 기반 RAG의 중요성
- pip-tools로 lock 파일 없는 환경에서 의존성 잠그기

블로그는 면접 단골 질문인 "왜 그렇게 만들었나요?"의 사전 답변 역할을 한다.

## 28. README 구조

README는 기술 나열이 아니라 판단 근거와 트레이드오프를 보여줘야 한다.

````markdown
# Tax-Copilot

세무사를 위한 AI 코파일럿. 반복 업무는 자동화하고, 최종 판단은 세무사가 합니다.

> 본 시스템은 세무사의 업무를 보조하는 도구이며, 모든 세무 판단의 최종 책임은
> 사용 세무사에게 있습니다. AI가 제공하는 분석 결과는 참고용 후보이며,
> 세무신고 및 세무대리는 세무사법에 따라 세무사 자격이 있는 자만이 수행할 수
> 있습니다.

## What It Does

- 영수증 업로드
- AI 필드 추출
- 거래일 기준 세법 RAG
- 결정론적 세액 계산
- 고위험 거래 HITL 검토
- 판단 근거와 감사 로그 저장

## Demo

[15~20초 GIF]

## Architecture

[light/dark architecture diagram]

## Key Engineering Decisions

### 왜 LangGraph인가

HITL처럼 실행을 멈추고 외부 입력으로 재개하는 상태 기반 workflow가 필요했기 때문이다.

### 왜 거래일 기준 법령 검색인가

세무 판단은 현재 법령이 아니라 거래일 당시 시행 법령 기준으로 재현 가능해야 하기 때문이다.

### 왜 LLM 계산을 금지했는가

세액 계산 오차는 실제 금전 리스크로 이어지므로 Python deterministic tool로 처리한다.

### 왜 헥사고날 아키텍처인가

세무 도메인 로직이 외부 시스템(LLM, vector DB, OCR) 변경에 영향받지 않도록 분리한다.
이 덕분에 세액 계산 로직은 mock 없이 결정론적으로 테스트할 수 있다.

### 왜 free-tier-first인가

포트폴리오 단계에서는 비용을 통제하되, 사용량 계측과 유료 전환 경로를 설계해둔다.

## Local Development

```bash
cp .env.example .env.dev
docker compose up -d
pip install -r requirements/dev.txt
pip install -e .
alembic upgrade head
python scripts/init_checkpointer.py
uvicorn tax_copilot.main:app --reload
```

## Evaluation

RAGAS와 KPI는 샘플 데이터 구축 후 실측값만 기재한다.

## Roadmap

- Semantic Cache
- RAGAS
- 법령 자동 업데이트
- SSE/WebSocket 알림
- KPI dashboard
- OpenTelemetry 분산 trace
````

## 29. 부록 - 공식 문서 확인 링크

- Gemini 2.5 Flash: https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash
- Gemini Embeddings: https://ai.google.dev/gemini-api/docs/embeddings
- LangGraph Interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangGraph PostgresSaver setup: https://reference.langchain.com/python/langgraph.checkpoint.postgres/PostgresSaver/setup
- Qdrant Cloud free cluster: https://qdrant.tech/documentation/cloud/create-cluster/
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Next.js Route Handlers: https://nextjs.org/docs/app/api-reference/file-conventions/route
- Celery Tasks: https://docs.celeryq.dev/en/stable/userguide/tasks.html
- law.go.kr Open API: https://open.law.go.kr/LSO/openApi/guideResult.do
- pip-tools: https://github.com/jazzband/pip-tools
- structlog: https://www.structlog.org/
- Michael Nygard ADR template: https://github.com/joelparkerhenderson/architecture-decision-record
- 세무사법: https://www.law.go.kr/법령/세무사법


---

## 관련 문서

- **DESIGN_INDEX.md** — 전체 프로젝트 1~200줄 요약 (이것부터 읽기)
- **DESIGN_CORE.md** — 개요, 원칙, 법적 포지셔닝, MVP, 기술 결정, 스택, 아키텍처, 폴더 구조, 도메인 모델 (1~9장)
- **DESIGN_AGENT.md** — LangGraph, HITL, RAG, 법령 수집, Vision, Celery (10~15장)
- **DESIGN_OPS.md** — DB, 인증, 관측, Graceful Degradation, 테스트, 배포 (16~21장)
- **DESIGN_PLAN.md** — 개발 로드맵, 일정, 백로그, 함정, 시연 자료, README, 부록 (22~29장)
