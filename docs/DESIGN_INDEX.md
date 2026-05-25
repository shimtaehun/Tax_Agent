# Tax-Copilot Design — INDEX

전체 설계 문서의 압축 요약본. 새 대화를 시작할 때 이 파일만 먼저 로드하고, 상세 작업 시 해당 모듈만 추가 로드한다.

Version: 5.1 (분할판)
Author: 심태훈 / Tax-Copilot Portfolio Project
일정: 2026-05-24 ~ 2026-06-27 (5주, 약 150h)

---

## 1. 프로젝트 정체성

**한 줄 정의**: 세무사를 위한 AI 기반 업무 자동화 워크플로우 엔진. "대체가 아닌 증폭, 세무사의 판단을 보조하는 AI 코파일럿."

**핵심 기능**: 영수증 이미지 업로드 → Vision으로 필드 추출 → 거래일 기준 법령 검색 → 부가세/법인세/계정과목 판단 후보 생성 → HITL 검토 → 감사 로그 저장.

**포트폴리오 포지셔닝**: 상태 기반 AI 워크플로우, 시점 기반 RAG, HITL interrupt/resume, Celery 장기 작업, 감사 가능성, free-tier-first 비용 통제.

→ 상세: `DESIGN_CORE.md` 1장

---

## 2. 절대 원칙 (위반 시 설계 폐기)

1. **Deterministic Calculation**: LLM은 계산하지 않는다. 금액은 `Decimal` 또는 정수 원 단위.
2. **법적 면책**: AI 출력은 "판단 후보"이지 결론이 아니다. 모든 최종 판단은 세무사가. 면책 문구는 README/로그인/영수증 화면/API 응답/감사 로그 export 5곳에 노출.
3. **시점 기반 RAG**: 법령 검색은 `now`가 아니라 **거래일(`as_of_date`)** 기준. `effective_from <= as_of_date < effective_to`.
4. **HITL 분리 패턴**: `audit_prepare_node` (LLM, 저장) → `human_review_node` (interrupt만) → `save_result_node` (resume 후 저장). interrupt 노드 안에서 LLM/DB/외부 API 호출 금지 (resume 시 재실행됨).
5. **Idempotency**: Celery task는 `acks_late` + Redis lock + DB status check. worker 강제 종료해도 중복 처리 없음.

→ 상세: `DESIGN_CORE.md` 2~3장, `DESIGN_AGENT.md` 10~11장

---

## 3. 확정된 기술 결정 (변경 시 ADR)

| 항목 | 결정 |
| --- | --- |
| Python | 3.11 |
| 패키지 관리 | pip + pip-tools (`requirements/*.in` → `*.txt`). uv/Poetry 아님. |
| 백엔드 | FastAPI (async), SQLAlchemy 2.0 async, Alembic |
| DB | PostgreSQL 16 (Checkpointer 포함), Redis 7 (Celery broker + lock) |
| 벡터 DB | Qdrant (MVP는 in-memory → Qdrant 교체) |
| 임베딩 | `gemini-embedding-2` 기본, `gemini-embedding-001` fallback. dim 768. |
| AI 워크플로우 | LangGraph + PostgreSQL Checkpointer |
| Vision | Gemini Vision (structured output) |
| 비동기 | Celery + Redis |
| 프론트엔드 | Next.js App Router (Week 5에만 작업) |
| 코드 품질 | ruff (E,F,I,B,UP,S, line 100) + mypy (core strict) + pre-commit |
| 배포 | Railway 1순위 / Render 2순위, Dockerfile 기반 |
| 스토리지 | 로컬 우선, 이후 Cloudflare R2 adapter 교체 |

→ 상세: `DESIGN_CORE.md` 5~6장

---

## 4. 아키텍처 요점

**헥사고날**. `src/core/` (도메인, 의존성 없음) ← `src/infra/` (DB, Qdrant, Gemini, R2 어댑터) ← `src/api/` (FastAPI) / `src/workers/` (Celery). 의존성은 한 방향, core는 외부를 모른다.

**상태**: `AgentState`에 원본 이미지 bytes 넣지 않음. `file_path`, `receipt_id`, `thread_id`, `corpus_version`만.

**파일 최대 400줄, 함수 50줄, 파라미터 5개**.

→ 상세: `DESIGN_CORE.md` 7~9장 (도메인 모델/`ParsedReceipt`/`evidence_type` 포함)

---

## 5. LangGraph 그래프

```
[START] → image_quality → (unreadable: reject)
        → intake → build_retrieval_query → tax_law_retrieval
        → calculation → audit_prepare
        → (requires_human: human_review[interrupt] → save_result)
        → (low_risk_candidate: save_result) → [END]
```

`low_risk_candidate`는 자동 확정이 아니라 판단 후보 저장 경로다. 사용자에게는 "판단 후보 작성 완료" 또는 "검토 가능" 상태로 표시한다.

resume는 `Command(resume={"approved": True, "comment": ...})` + `config={"configurable": {"thread_id": ...}}`.

→ 상세: `DESIGN_AGENT.md` 10~11장

---

## 6. RAG 핵심

- 검색은 거래일 기준 (`effective_from <= as_of_date`, `effective_to > as_of_date OR is_current`).
- `chunk_id`에 시행일/corpus version 포함 (예: `vat-20240101-art39-p1-sub4-7f3a9c`).
- 모델 변경 시 전체 corpus 재임베딩 (embedding space 호환 안 됨).
- Reranker는 MVP 후순위. dense retrieval만으로 먼저 측정 → FlashRank 비교 → 한국어 reranker 검토.
- 데이터 소스: law.go.kr API 1순위, 예규/질의회신은 수동 선별.
- PostgreSQL fallback에서 한국어 FTS configuration 있다고 가정하지 않음 (`ILIKE` / `pg_trgm` / PGroonga 검토).

→ 상세: `DESIGN_AGENT.md` 12~13장

---

## 7. 운영 / 관측

- 로깅: `structlog` JSON, request_id contextvar, PII 마스킹 (사업자번호/카드번호).
- 예외: 도메인 예외 계층 (`TaxCopilotError` → `ValidationError`/`ExternalServiceError`/...).
- 감사 로그: 모든 상태 전이를 `audit_events` 테이블에 기록.
- Graceful Degradation: Gemini/Qdrant/Redis 장애 시 HITL fallback.
- Rate limiting, API 버저닝 (`/v1/...`), 시크릿은 플랫폼 환경변수.
- 데이터 보호: 사업자번호/카드번호 마스킹, 세무자료 5년 보존 옵션.

→ 상세: `DESIGN_OPS.md` 16~21장

---

## 8. 5주 일정

| 주차 | Phase | 산출물 |
| --- | --- | --- |
| W1 | Phase 0 + 1 전반 | repo skeleton, Docker Compose, Alembic, seed admin/default client, local upload |
| W2 | Phase 1 후반 + 2 | Receipt upload, mock Vision/RAG, LangGraph state, HITL, audit log |
| W3 | Phase 3 | sample law corpus, Gemini embedding, 거래일 검색, Qdrant adapter |
| W4 | Phase 4 + 5 | Gemini Vision, Celery, Redis lock, idempotency |
| W5 | Phase 6 | Next.js UI, Railway 배포, README, demo |

가용: 평일 2h × 5 + 주말 10h × 2 = 30h/주. 매주 일요일 점검·조정.

**Phase 0 (Week 1) 9개 step**: repo 초기화 → pip-tools → ruff/mypy/pre-commit → Docker Compose → FastAPI skeleton → SQLAlchemy/Alembic → structlog → GitHub Actions → ADR 회고.

→ 상세: `DESIGN_PLAN.md` 22~23장

---

## 9. MVP 의도적으로 미루는 것 (백로그)

Semantic Cache, 자동 법령 업데이트 GHA, RAGAS 정량 평가, KPI 대시보드, Unstructured API 문서 파싱, WebSocket 알림, Circuit Breaker, 대규모 예규 수집, data.go.kr 통계, 국회 의안정보시스템.

→ 상세: `DESIGN_CORE.md` 4장, `DESIGN_PLAN.md` 24~25장

---

## 10. 시연 / 포트폴리오 자료

- README: 한 줄 소개 → demo GIF (15s) → architecture diagram (light/dark SVG) → Key Engineering Decisions 4~5개 → 스택 → Local Dev → Roadmap.
- ADR 최소 5개: LangGraph 선택 / 거래일 기반 검색 / PostgreSQL Checkpointer / 헥사고날 / pip-tools.
- 면접 talking points: 가장 어려웠던 결정, LangGraph 선택 이유, 거래일 검색 구현, 잘못된 판단 대응, 비용, 시스템 한계, 가장 많이 배운 부분.

→ 상세: `DESIGN_PLAN.md` 26~29장

---

## 11. 모듈 라우팅 (작업 종류별)

| 작업 | 로드할 파일 |
| --- | --- |
| 새 세션 동기화 | INDEX만 |
| 도메인 모델, MVP 범위, 기술 결정 변경 | INDEX + CORE |
| LangGraph 노드, HITL, RAG, Celery 작업 | INDEX + AGENT |
| DB 스키마, 인증, 로깅, 배포 | INDEX + OPS |
| 일정 조정, ADR 작성, README 작업 | INDEX + PLAN |
| 도메인 모델과 에이전트 동시 수정 | INDEX + CORE + AGENT |

원본 통째 로드는 피한다 (~40K 토큰). 모듈 단위로 잘라 쓰면 평균 8~15K 토큰.

---

## 12. 변경 이력 관리

- 설계 결정 변경 시: 해당 모듈에 반영 + `docs/adr/NNNN-*.md` 작성 + 본 INDEX의 관련 줄 업데이트.
- 섹션 확정 완료 시: 본문을 3~5줄 요약으로 축약하고 "상세는 git history 참조" 명시.
- v5.0 변경: 법적 포지셔닝 / 확정 기술 결정 / 폴더 구조 / 관측 / 배포 확장 / 5주 일정 / 시연 자료 신설. `evidence_type` 추가. CLAUDE.md 분리.
- v5.1 변경: 2026-05-24 기준 일정 재산정. mock 기반 수직 슬라이스 우선, local storage first, 자동 승인 표현 제거, Qdrant/R2/Celery는 수직 슬라이스 이후 연동으로 조정.
