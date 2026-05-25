# Tax-Copilot Design — CORE (1~9장)

본 문서는 전체 설계 문서를 4개 모듈 + 1개 인덱스로 분할한 것 중 **CORE 모듈**입니다.
이 파일만 단독으로 로드해도 프로젝트의 정체성, MVP 범위, 기술 결정, 아키텍처, 도메인 모델까지 파악 가능합니다.
LangGraph 에이전트, RAG, DB, 배포 등 상세는 별도 파일을 참조하세요.

Version: 5.1 (분할판)
Author: 심태훈 / Tax-Copilot Portfolio Project

---

﻿# Tax-Copilot Master Design Document

세무사를 위한 AI 기반 업무 자동화 워크플로우 엔진

Version: 5.1
Last Updated: 2026-05-15
Author: 심태훈 / Tax-Copilot Portfolio Project
Repository: tax-copilot

## 핵심 슬로건

"대체가 아닌 증폭. 세무사의 판단을 보조하는 AI 코파일럿"

## v5.0 변경 사항

v4.0 Revised에서 다음 항목이 추가 또는 보강되었다.

- 3장 법적 포지셔닝과 면책 신설 (세무사법 리스크 대응)
- 5장 확정된 기술 결정 신설 (Python 3.11, pip + requirements, Docker Compose 등)
- 8장 폴더 구조와 의존성 방향 신설 (헥사고날 아키텍처 적용)
- 18장 관측 가능성과 에러 처리 신설 (structlog, 도메인 예외, PII 마스킹)
- 21장 배포·비용·환경 분리 확장 (Render/Railway, 시크릿 관리, API 버저닝, rate limiting)
- 23장 5주 일정과 Phase 0 분해 신설
- 27장 포트폴리오 마감과 시연 자료 신설
- ParsedReceipt에 적격증빙 종류(evidence_type) 추가
- 각 Phase에 학습 목표 추가
- AI 페어 프로그래밍 규칙은 별도 CLAUDE.md로 분리

## 목차

1. 프로젝트 개요
2. 핵심 엔지니어링 원칙
3. 법적 포지셔닝과 면책
4. MVP 범위와 후순위 범위
5. 확정된 기술 결정
6. 통합 기술 스택
7. 시스템 아키텍처
8. 폴더 구조와 의존성 방향
9. 도메인 모델과 판단 스키마
10. LangGraph 에이전트 설계
11. HITL 설계
12. RAG 파이프라인
13. 법령 수집과 버전 관리
14. 영수증 파일 처리와 Vision 파이프라인
15. 비동기 처리와 Celery
16. 데이터베이스 스키마
17. 인증, 보안, 감사 로그
18. 관측 가능성과 에러 처리
19. Graceful Degradation
20. 테스트 전략
21. 배포·비용·환경 분리
22. 개발 로드맵
23. 5주 일정과 Phase 0 분해
24. 후순위 기능 백로그
25. 제거 또는 축소할 항목
26. 알려진 함정과 해결책
27. 포트폴리오 마감과 시연 자료
28. README 구조
29. 부록 - 공식 문서 확인 링크

## 1. 프로젝트 개요

### 문제 정의

세무사 업무에는 영수증 분류, 기초 기장 입력, 증빙 적격성 검토, 세법 조문 검색처럼 반복적이지만 실수 비용이 큰 작업이 많다. 이 반복 업무가 세무사의 시간을 잠식하여 절세 전략, 리스크 상담, 고객 커뮤니케이션 같은 고부가가치 업무에 집중하기 어렵게 만든다.

### 해결 방안

Tax-Copilot은 영수증과 거래 정보를 받아 다음 작업을 자동화한다.

- 영수증 이미지에서 날짜, 거래처, 금액, 품목, 결제수단 추출
- 거래일 기준으로 시행 중이던 법령과 예규 검색
- 부가세 매입세액 공제 가능성, 법인세 손금산입 가능성, 계정과목 후보 판단
- 계산은 Python deterministic tool로 수행
- 모호하거나 고위험인 경우 세무사에게 HITL 검토 요청
- 모든 판단에 법령 근거와 감사 로그 저장

### 포트폴리오 포지셔닝

이 프로젝트는 단순 CRUD 앱이 아니라 다음 역량을 보여주는 포트폴리오다.

- 상태 기반 AI 워크플로우 설계
- 법령 버전 관리가 포함된 RAG
- HITL interrupt/resume 구조
- Celery 기반 장기 실행 AI 작업 처리
- 세무 도메인에서 요구되는 감사 가능성과 재현성
- 비용을 통제하는 free-tier-first 아키텍처

## 2. 핵심 엔지니어링 원칙

### Rule 1. Deterministic Calculation

LLM은 계산하지 않는다. LLM은 필요한 값과 판단 후보를 추출하고, 세액 계산과 한도 계산은 Python 함수가 담당한다.

세무 도메인에서 `float` 계산은 피한다. 금액은 정수 원 단위 또는 `Decimal`로 처리한다.

```python
from decimal import Decimal, ROUND_DOWN
from langchain_core.tools import tool

@tool
def calculate_vat_from_supply_value(
    supply_value_krw: int,
    tax_rate_basis_points: int = 1000,
) -> dict:
    """Calculate VAT amount from supply value.

    tax_rate_basis_points=1000 means 10.00%.
    LLM must call this tool instead of computing VAT directly.
    """
    rate = Decimal(tax_rate_basis_points) / Decimal(10000)
    vat = (Decimal(supply_value_krw) * rate).quantize(
        Decimal("1"),
        rounding=ROUND_DOWN,
    )
    return {
        "supply_value_krw": supply_value_krw,
        "vat_krw": int(vat),
        "total_krw": supply_value_krw + int(vat),
        "tax_rate_basis_points": tax_rate_basis_points,
    }
```

### Rule 2. Grounded and Versioned RAG

AI는 검색된 법령과 예규 근거 안에서만 판단한다. 더 중요하게는 "거래일 당시 적용 법령"을 기준으로 검색해야 한다.

잘못된 예:

```python
effective_date <= datetime.now()
```

올바른 방향:

```python
effective_from <= receipt_date < effective_to
```

`effective_to`가 없는 현행 법령은 충분히 먼 미래 날짜 또는 `None`으로 표현하고, 검색 함수에서 명시적으로 처리한다.

### Rule 3. Human Accountability

AI는 세무사를 대체하지 않는다. AI는 판단 후보와 근거를 제시하고, 최종 책임이 필요한 영역은 세무사에게 이관한다.

HITL 이관 기준:

- 검색 근거 없음
- 법령과 예규가 상충
- confidence < 0.75
- 고위험 업종 또는 거래처
- 접대비, 유흥, 골프, 카지노, 심야 결제
- 금액이 내부 기준 이상
- 영수증 품질 불량
- 동일 파일 또는 유사 거래 중복 의심

### Rule 4. Auditability and Reproducibility

세무 판단은 나중에 다시 설명할 수 있어야 한다. 따라서 다음 데이터를 저장한다.

- 사용한 프롬프트 버전
- 사용한 모델명과 모델 버전
- 법령 corpus version
- 검색된 chunk id 목록
- 실제 인용한 조문 id
- 거래일 기준 적용 법령 버전
- AI 판단, 사람 판단, 변경 사유
- 모든 상태 전이 이벤트

### Rule 5. Privacy by Design

영수증과 세무 정보는 민감 데이터다. 외부 API 전송, 파일 저장, 로그 기록, presigned URL 발급은 최소 권한과 최소 보관 원칙을 따른다.

## 3. 법적 포지셔닝과 면책

### 세무사법 리스크

세무사법 제2조와 제20조는 세무대리 업무를 세무사 자격이 있는 자만 수행할 수 있도록 제한한다. AI 시스템이 직접 "이 거래는 손금산입 가능하다" 같은 결론을 사용자(세무사가 아닌 자)에게 제공하면 무자격 세무대리 논란이 발생할 여지가 있다.

본 프로젝트는 이 리스크를 다음 설계로 회피한다.

- 사용자는 세무사 또는 세무법인 소속 직원으로 한정
- AI 출력은 "판단 후보"와 "법령 근거"이며, 확정 결론이 아니다
- 모든 최종 판단은 세무사 검토 또는 HITL 승인을 거친다
- HITL 없이 흐름을 마치는 경우도 "자동 승인"이 아니라 "판단 후보 작성 완료"로 표시한다. MVP에서 최종 확정은 세무사 또는 관리자 검토 상태로만 표현한다.

### 면책 명시 위치

다음 위치에 면책 문구를 반드시 노출한다.

- README.md 상단
- 로그인 화면
- 영수증 상세 화면 하단
- API 응답의 메타 필드(`disclaimer`)
- 감사 로그 export 결과의 첫 페이지

### 면책 문구 표준 (한국어)

> 본 시스템은 세무사의 업무를 보조하는 도구이며, 모든 세무 판단의 최종 책임은 사용 세무사에게 있습니다. AI가 제공하는 분석 결과는 참고용 후보이며, 세무신고 및 세무대리는 세무사법에 따라 세무사 자격이 있는 자만이 수행할 수 있습니다.

### 데이터 보호 관련

- 개인정보보호법: 사업자번호와 카드번호 등 식별정보는 마스킹 또는 암호화
- 신용정보법: 신용카드 매출전표 정보는 별도 저장 분리 검토
- 세무자료 보존: 법정 보존기간(5년) 동안 삭제 금지 옵션 제공

## 4. MVP 범위와 후순위 범위

### MVP에서 반드시 구현할 것

MVP는 작게 만들되 핵심 구조를 끝까지 연결한다. 우선순위는 "외부 서비스 연동"보다 "업로드부터 사람 검토까지 끊기지 않는 수직 슬라이스"다.

- seed admin/default client 또는 단순 JWT 기반 로그인과 admin 역할 분리
- 영수증 업로드 API
- magic bytes 기반 파일 검증과 로컬 스토리지 저장
- Receipt, TaxJudgment, AuditEvent DB 모델
- LangGraph 기본 흐름
- mocked Vision 기반 영수증 필드 추출
- mocked 또는 in-memory RAG 기반 법령 후보 반환
- 거래일 기준 법령 필터
- 결정론적 계산 함수와 판단 후보 저장
- HITL 검토/승인/반려 API
- 모든 상태 전이에 대한 감사 로그 저장
- 전체 흐름 통합 테스트

### MVP 이후 바로 붙일 것

수직 슬라이스가 테스트에서 통과한 뒤 다음 외부 연동을 붙인다.

- Gemini Vision structured extraction
- 법령 chunk 20개 내외의 시연용 sample corpus
- Qdrant 검색 어댑터
- Celery 작업 dispatch와 Redis lock
- Cloudflare R2 스토리지 어댑터

sample corpus는 구조 시연용이며, 세무 판단 정확도를 주장하는 근거로 쓰지 않는다.

### MVP에서 의도적으로 미룰 것

다음은 좋은 기능이지만 MVP의 핵심 검증을 늦춘다.

- Semantic Cache
- 자동 법령 업데이트 GitHub Actions
- RAGAS 정량 평가
- KPI 대시보드
- Unstructured API 문서 파싱
- WebSocket 실시간 알림
- Circuit Breaker
- 대규모 예규/질의회신 수집
- data.go.kr 통계 대시보드
- 국회 의안정보시스템 연동

## 5. 확정된 기술 결정

본 프로젝트의 출발점에서 확정된 결정 사항이다. 변경 시 ADR로 기록한다.

### 5.1. 언어 및 런타임

| 항목 | 값 | 이유 |
| --- | --- | --- |
| Python | 3.11 | LangGraph, FastAPI, Pydantic v2 안정 지원. Render/Railway 빌더 검증됨. |
| Node.js | 20 LTS | Next.js App Router 권장 |

### 5.2. 패키지 및 의존성 관리

- pip + `requirements/` 디렉토리 구조
- pip-tools로 `.in` → `.txt` lock 생성
- 환경별 분리: `base.in`, `dev.in`, `prod.in`

uv 또는 Poetry 대신 pip-tools를 선택한 이유는 팀 onboarding 부담이 적고, Render/Railway 기본 빌더가 `requirements.txt`를 그대로 받기 때문이다. 필요 시 uv로 마이그레이션 가능한 구조다.

### 5.3. 개발 환경

- Docker Compose로 PostgreSQL 16 + Redis 7 컨테이너 실행
- 애플리케이션 코드는 호스트에서 실행하거나 Compose 안에서 실행 (둘 다 지원)
- `.env` 파일은 git에서 제외, `.env.example`은 추적

### 5.4. 코드 품질

| 도구 | 역할 | 설정 |
| --- | --- | --- |
| ruff format | formatter | line-length 100 |
| ruff check | linter | E, F, I, B, UP, S 규칙셋 |
| mypy | type check | core 모듈 strict, scripts non-strict |
| pre-commit | git hook | 모든 commit 전 자동 실행 |

### 5.5. 코드 스타일

- Docstring: Google style, 영어
- 인라인 주석: 한국어 (도메인 용어는 한국어가 더 정확)
- Naming: PEP 8 준수 (snake_case 함수/변수, PascalCase 클래스, SCREAMING 상수)
- 함수 최대 50줄, 파라미터 최대 5개
- 파일 최대 400줄

### 5.6. Git 협업

- 커밋: Conventional Commits (`feat(scope): ...`)
- 브랜치: `main` (always deployable), `feat/{phase}-{feature}`
- PR: 1 PR = 1 논리 단위, 600 lines 이하 권장
- 1인 작업이지만 PR 분리를 연습한다 (포트폴리오 평가에 반영)

### 5.7. 배포

- 목표: Railway 또는 Render. 둘 다 제한적 무료/크레딧 기반이며, 장기 배포는 소액 유료 전환 가능성을 전제한다.
- 컨테이너 기반 (Dockerfile 사용)
- DB는 Render PostgreSQL 또는 Railway PostgreSQL
- Redis는 Upstash Redis free tier 또는 Render Redis

### 5.8. 프론트엔드 진행 방식

- Week 1~4: 백엔드 + LangGraph + RAG에 집중. API 테스트는 curl/httpie/Postman
- Week 5: Next.js로 최소 UI 구현 (로그인, 영수증 업로드, admin 검토)

## 6. 통합 기술 스택

### Backend

| 기술 | 역할 | 비고 |
| --- | --- | --- |
| FastAPI | API 서버 | async 기반 |
| SQLAlchemy 2.x | ORM | async session 사용 |
| Alembic | DB migration | Checkpointer setup과 별도 |
| PostgreSQL 16 | 메인 DB | 앱 데이터, 감사 로그, LangGraph checkpoint |
| Redis 7 | Celery broker/result, lock | 초기에는 broker 중심 |
| Celery | 장기 실행 AI 작업 | HTTP 요청과 AI 처리 분리 |
| structlog | 구조화 로깅 | JSON 출력, request_id 전파 |

### AI Workflow

| 기술 | 역할 | 비고 |
| --- | --- | --- |
| LangGraph | 상태 기반 agent workflow | HITL interrupt/resume |
| Pydantic v2 | structured output 검증 | LLM 응답 스키마 강제 |
| Gemini 2.5 Flash | Vision 및 추론 | 2026년 기준 stable model |
| LangSmith | tracing | 후순위지만 early integration 가능 |

Gemini 2.5 Flash는 문서상 text, image, video, audio input과 structured output, function calling을 지원한다. 모델 정보는 배포 시점에 다시 확인한다.

참고: https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash

### RAG

| 기술 | 역할 | 비고 |
| --- | --- | --- |
| Gemini Embedding | 문서/쿼리 임베딩 | 기본 `gemini-embedding-2`, 필요 시 `gemini-embedding-001` fallback |
| Qdrant Cloud | vector DB | free tier는 prototype용 |
| FlashRank 또는 대체 reranker | reranking | 한국어 성능 검증 후 채택 |
| PostgreSQL | 법령 원문 snapshot, fallback search | FTS 한국어 설정 주의 |

Gemini embedding은 2026년 기준 `gemini-embedding-2`를 기본으로 사용한다. 공식 문서상 stable 모델이며, 입력 토큰 한도는 8,192이고 출력 차원은 128~3072를 지원한다. 이 프로젝트는 저장 비용과 검색 성능의 균형을 위해 `output_dimensionality=768`을 우선 사용한다. `gemini-embedding-001`은 text-only fallback 후보로만 둔다. Qdrant collection dimension과 embedding output dimension은 반드시 일치해야 한다.

참고: https://ai.google.dev/gemini-api/docs/embeddings

### Frontend

| 기술 | 역할 |
| --- | --- |
| Next.js 14+ App Router | 업로드 화면, admin 대시보드 |
| Polling | MVP HITL 상태 갱신 |
| SSE 또는 WebSocket | 후순위 실시간 알림 |

MVP에서는 5초 polling으로 충분하다. Next.js Route Handler는 HTTP method 중심이므로 WebSocket 서버를 Next.js에 억지로 넣지 않는다. 실시간성이 필요하면 FastAPI SSE, 별도 realtime provider, 또는 WebSocket 서버를 검토한다.

참고: https://nextjs.org/docs/app/api-reference/file-conventions/route

### Storage

| 기술 | 역할 | 비고 |
| --- | --- | --- |
| Local storage | MVP 영수증 파일 저장 | 먼저 구현해서 업로드 흐름을 고정 |
| Cloudflare R2 | 배포용 영수증 파일 저장 | S3-compatible adapter로 교체 |

R2 free tier는 Standard storage 기준 10GB-month, Class A 1M requests/month, Class B 10M requests/month를 제공한다. 무료 조건은 바뀔 수 있으므로 README에는 실측 비용과 기준일을 함께 적는다.

참고: https://developers.cloudflare.com/r2/pricing/

## 7. 시스템 아키텍처

```text
[Next.js Client]
  - receipt upload
  - admin review dashboard
  - polling

        |
        v

[FastAPI]
  - auth
  - upload validation
  - receipt CRUD
  - admin review API
  - task status API

        |
        v

[Storage: Local -> R2 adapter]
  - private receipt files
  - local path in MVP
  - presigned access only after R2 integration

[PostgreSQL]
  - users
  - tenants
  - receipts
  - judgments
  - law snapshots
  - audit events
  - LangGraph checkpoints

[Redis]
  - Celery broker
  - result backend
  - distributed lock

        |
        v

[Celery Worker]
  - idempotent receipt processing
  - timeout handling
  - retry

        |
        v

[LangGraph]
  - intake
  - tax law retrieval
  - calculation
  - audit prepare
  - human review interrupt
  - save result

        |
        v

[External Services]
  - Gemini Vision / LLM
  - Gemini Embedding
  - Qdrant
  - law.go.kr
  - LangSmith
```

핵심 역할 분리:

- Celery: 언제 실행할 것인가
- LangGraph: 어떤 순서와 조건으로 실행할 것인가
- PostgreSQL Checkpointer: 어디까지 실행했는가
- Audit Event: 누가 어떤 판단을 했는가

## 8. 폴더 구조와 의존성 방향

### 8.1. 전체 폴더 구조

```text
tax-copilot/
├── backend/
│   ├── src/
│   │   └── tax_copilot/
│   │       ├── __init__.py
│   │       ├── main.py                    # FastAPI entry, lifespan
│   │       ├── config/
│   │       │   ├── settings.py            # pydantic-settings
│   │       │   └── logging.py             # structlog config
│   │       ├── api/
│   │       │   ├── deps.py                # 공통 의존성 (auth, db)
│   │       │   ├── errors.py              # 예외 핸들러
│   │       │   └── v1/
│   │       │       ├── receipts.py
│   │       │       ├── reviews.py         # HITL endpoints
│   │       │       ├── auth.py
│   │       │       └── admin.py
│   │       ├── core/                      # 도메인 로직 (외부 의존성 X)
│   │       │   ├── tax/
│   │       │   │   ├── decisions.py       # TaxDecision 도메인 객체
│   │       │   │   ├── calculations.py    # Decimal 기반 세액 계산
│   │       │   │   └── rules.py           # 한도, risk flag 판정
│   │       │   ├── receipts/
│   │       │   │   ├── validation.py      # magic bytes, size
│   │       │   │   └── parsing.py
│   │       │   └── exceptions.py          # 도메인 예외 계층
│   │       ├── infra/                     # 외부 시스템 어댑터
│   │       │   ├── db/
│   │       │   │   ├── session.py
│   │       │   │   ├── models/            # SQLAlchemy 모델
│   │       │   │   └── repositories/      # CRUD 계층
│   │       │   ├── storage/
│   │       │   │   └── r2.py
│   │       │   ├── llm/
│   │       │   │   ├── gemini.py
│   │       │   │   └── prompts/           # 프롬프트 버전 관리
│   │       │   ├── vector/
│   │       │   │   └── qdrant.py
│   │       │   └── cache/
│   │       │       └── redis.py
│   │       ├── agents/                    # LangGraph
│   │       │   ├── state.py
│   │       │   ├── graph.py
│   │       │   ├── nodes/
│   │       │   │   ├── intake.py
│   │       │   │   ├── retrieval.py
│   │       │   │   ├── calculation.py
│   │       │   │   ├── audit_prepare.py
│   │       │   │   ├── human_review.py
│   │       │   │   └── save_result.py
│   │       │   └── tools/                 # @tool 함수들
│   │       │       ├── vat.py
│   │       │       └── entertainment_limit.py
│   │       ├── rag/
│   │       │   ├── chunking.py
│   │       │   ├── embedding.py
│   │       │   ├── retrieval.py
│   │       │   └── reranker.py
│   │       ├── workers/
│   │       │   ├── celery_app.py
│   │       │   └── tasks/
│   │       │       └── receipts.py
│   │       ├── auth/
│   │       │   ├── jwt.py
│   │       │   ├── password.py
│   │       │   └── permissions.py
│   │       ├── audit/
│   │       │   └── events.py
│   │       └── schemas/                   # Pydantic API 스키마 (도메인과 분리)
│   │           ├── receipts.py
│   │           └── reviews.py
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   ├── fixtures/
│   │   └── conftest.py
│   ├── migrations/                        # Alembic
│   ├── scripts/
│   │   ├── 01_collect_laws.py
│   │   ├── 02_normalize_law_versions.py
│   │   ├── 03_chunk_laws.py
│   │   ├── 04_embed_chunks.py
│   │   ├── 05_upload_to_qdrant.py
│   │   └── init_checkpointer.py
│   ├── requirements/
│   │   ├── base.in
│   │   ├── base.txt
│   │   ├── dev.in
│   │   ├── dev.txt
│   │   ├── prod.in
│   │   └── prod.txt
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                              # Next.js
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
├── docs/
│   ├── adr/                               # Architecture Decision Records
│   │   ├── 0001-why-langgraph.md
│   │   ├── 0002-why-postgres-checkpointer.md
│   │   └── 0003-why-transaction-date-retrieval.md
│   ├── CONTRIBUTING.md
│   ├── CODING_STYLE.md
│   ├── ARCHITECTURE.md
│   └── LEARNING_NOTES/                    # Phase별 학습 기록
│       ├── phase0-setup.md
│       └── phase1-core.md
├── docker-compose.yml
├── .env.example
├── .pre-commit-config.yaml
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── test.yml
├── CLAUDE.md                              # AI 페어 프로그래밍 규칙
├── README.md
└── Makefile                               # 자주 쓰는 명령어
```

### 8.2. 의존성 방향

```text
api/, workers/, agents/   ← 사용 계층 (HTTP, Celery, LangGraph)
        │
        ▼
infra/                    ← 외부 시스템 어댑터 (DB, LLM, Vector, Cache)
        │
        ▼
core/                     ← 순수 도메인 (외부 라이브러리 import 금지)
```

`core/`는 다음 모듈만 import할 수 있다.

- 표준 라이브러리
- pydantic (validation 책임은 도메인 영역)
- typing, datetime, decimal 등

`core/`에서 금지하는 import:

- sqlalchemy, asyncpg
- google.generativeai, openai, anthropic
- qdrant_client
- redis, celery
- fastapi, starlette

이렇게 분리하면 세무 도메인 로직을 mock 없이 단위 테스트할 수 있고, 외부 시스템이 바뀌어도 도메인 로직이 흔들리지 않는다.

### 8.3. src layout 사용 이유

flat layout 대신 `src/tax_copilot/` 구조를 채택하는 이유는 다음과 같다.

- editable install (`pip install -e .`)을 강제해서 import 경로가 실제 배포 환경과 일치
- 테스트 코드가 우연히 dev-only 의존성에 의존하는 사고를 사전 차단
- packaging.python.org 공식 권장 방식

## 9. 도메인 모델과 판단 스키마

기존 `is_deductible` 하나로는 부족하다. 세무 판단은 여러 축으로 분리한다.

### 주요 판단 축

- 부가세 매입세액 공제 가능 여부
- 법인세 손금산입 가능 여부
- 소득세 필요경비 가능 여부
- 계정과목 후보
- 적격증빙 여부와 종류
- 접대비/복리후생비/여비교통비/소모품비 등 분류
- 위험 플래그
- HITL 필요 여부

### Pydantic 스키마

```python
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field

EvidenceType = Literal[
    "tax_invoice",          # 세금계산서
    "invoice",              # 계산서
    "credit_card_slip",     # 신용카드 매출전표
    "cash_receipt",         # 현금영수증
    "simplified_receipt",   # 간이영수증
    "unknown",
]

class Citation(BaseModel):
    chunk_id: str
    law_name: str
    article_no: str | None = None
    paragraph_no: str | None = None
    effective_from: date
    effective_to: date | None = None
    quoted_text: str

class TaxDecision(BaseModel):
    vat_creditable: bool | None = Field(
        description="VAT input tax credit eligibility. None means cannot determine."
    )
    expense_deductible: bool | None = Field(
        description="Corporate income tax deductibility or necessary expense eligibility."
    )
    account_title: str | None = Field(
        description="Account title candidate (e.g., 접대비, 복리후생비, 소모품비)."
    )
    evidence_type: EvidenceType
    evidence_status: str = Field(
        description="One of: valid, insufficient, unreadable, unknown."
    )
    confidence: float = Field(ge=0.0, le=1.0)
    risk_flags: list[str] = []
    citations: list[Citation] = []
    requires_human_review: bool
    review_reason: str | None = None
    prompt_version: str
    model_name: str
    law_corpus_version: str
```

### ParsedReceipt 스키마

```python
from datetime import date, time
from pydantic import BaseModel

class ParsedReceipt(BaseModel):
    merchant_name: str | None
    merchant_business_no: str | None = None
    transaction_date: date | None
    transaction_time: time | None = None
    total_amount_krw: int | None
    supply_value_krw: int | None = None
    vat_amount_krw: int | None = None
    items: list[str] = []
    payment_method: str | None = None
    evidence_type: EvidenceType = "unknown"
    raw_ocr_text: str | None = None
    extraction_confidence: float
```

`evidence_type`은 적격증빙 판정과 직결되므로 ParsedReceipt 단계에서 분류한다. 신용카드 매출전표와 현금영수증은 적격증빙 요건을 충족할 가능성이 높지만, 사업 관련성, 불공제 항목, 면세 거래, 접대비 여부에 따라 최종 공제 가능 여부는 달라진다. 따라서 증빙 종류는 판단 근거 중 하나일 뿐 자동 승인 조건으로 사용하지 않는다.


---

## 관련 문서

- **DESIGN_INDEX.md** — 전체 프로젝트 1~200줄 요약 (이것부터 읽기)
- **DESIGN_CORE.md** — 개요, 원칙, 법적 포지셔닝, MVP, 기술 결정, 스택, 아키텍처, 폴더 구조, 도메인 모델 (1~9장)
- **DESIGN_AGENT.md** — LangGraph, HITL, RAG, 법령 수집, Vision, Celery (10~15장)
- **DESIGN_OPS.md** — DB, 인증, 관측, Graceful Degradation, 테스트, 배포 (16~21장)
- **DESIGN_PLAN.md** — 개발 로드맵, 일정, 백로그, 함정, 시연 자료, README, 부록 (22~29장)
