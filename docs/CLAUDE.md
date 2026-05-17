# CLAUDE.md

Tax-Copilot 프로젝트의 AI 페어 프로그래밍 협업 규칙. 이 파일은 Claude Code 또는 Claude.ai와 작업할 때 매 세션 첫 메시지에 참조한다. Codex는 `AGENTS.md`를 우선 읽으므로, Codex 작업용 지침은 repo root의 `AGENTS.md`에 별도로 둔다.

## 프로젝트 컨텍스트

- 프로젝트명: Tax-Copilot
- 목적: 세무사를 위한 AI 기반 업무 보조 도구 (포트폴리오)
- 기간: 2026-05-16 ~ 2026-06-20 (5주)
- 배포 목표: Render 또는 Railway
- 본 프로젝트는 학습 중심으로 진행한다. 완성보다 이해를 우선한다.

### 설계 문서 구조

마스터 설계 문서는 토큰 비용 통제를 위해 5개 모듈로 분할되어 있다. 전체를 한꺼번에 읽지 않는다.

- `docs/design/DESIGN_INDEX.md` — 압축 요약본 + 모듈 라우팅 표. 새 세션 동기화 시 **이것부터** 읽는다.
- `docs/design/DESIGN_CORE.md` — 개요, 원칙, 법적 포지셔닝, MVP, 기술 결정, 스택, 아키텍처, 폴더 구조, 도메인 모델 (1~9장)
- `docs/design/DESIGN_AGENT.md` — LangGraph, HITL, RAG, 법령 수집, Vision, Celery (10~15장)
- `docs/design/DESIGN_OPS.md` — DB, 인증, 관측, Graceful Degradation, 테스트, 배포 (16~21장)
- `docs/design/DESIGN_PLAN.md` — 로드맵, 5주 일정, 백로그, 함정, 시연 자료, README, 부록 (22~29장)

작업 종류별로 어떤 파일을 추가로 열지는 INDEX의 **모듈 라우팅 표**를 따른다.

## Claude가 지킬 규칙

### 출력 형식

- 코드 출력 시 불필요한 서론 금지
- 이모티콘 사용 금지
- 학습 요청이면 개념 먼저, 구현 요청이면 코드/패치 먼저
- 설명은 짧게, 한 번에 하나의 개념만 다룬다

### 결정 단계

- 되돌리기 어려운 아키텍처/보안/데이터 손실 결정은 코드를 쓰기 전에 질문한다
- 사소한 구현 선택은 설계 문서와 기존 코드 스타일을 기준으로 진행한다
- 새 라이브러리/패턴 도입 시: 왜 필요한지 + 대안 + 트레이드오프를 먼저 제시
- 답을 모르면 추측하지 않는다. "확인이 필요하다" 또는 "검색해야 한다"고 명시한다

### 학습 흐름

- 코드 완성보다 사용자의 학습 흐름을 우선한다
- 개념을 모르고 코드만 복사하게 만들지 않는다
- 사용자가 이해하지 못하는 부분은 다음 step으로 넘어가지 않는다

### 토큰 절약 규칙

설계 문서가 5개로 분할된 이유는 이 규칙을 지키기 위해서다.

- **새 세션 시작 시 `DESIGN_INDEX.md`만 먼저 읽는다.** 다른 모듈은 작업이 그 영역에 진입할 때 그때 연다.
- 작업 종류별 모듈 매핑:
  - 도메인 모델, MVP 범위, 기술 결정 → INDEX + CORE
  - LangGraph 노드, HITL, RAG, Celery → INDEX + AGENT
  - DB 스키마, 인증, 로깅, 배포 → INDEX + OPS
  - 일정 조정, ADR 작성, README → INDEX + PLAN
- 한 모듈 안에서도 관련 섹션 또는 100~180줄 단위로만 읽는다. 모듈 전체를 매번 훑지 않는다.
- 두 모듈 이상이 필요한 경우라도 동시에 3개 이상을 열지 않는다. 작업을 쪼개라.
- 검색은 `rg` / `rg --files`를 우선 사용한다.
- 터미널 출력은 핵심 에러 20~40줄만 확인한다.
- 코드 작성 전에는 관련 코드 파일 2~5개만 먼저 읽고, 추가 파일은 필요할 때만 연다.
- 이미 확인한 내용을 반복해서 다시 읽지 않는다.
- 테스트는 타깃 테스트부터 실행하고, 전체 테스트는 마무리 검증 때 실행한다.

## 사용자가 지킬 규칙

### Step 진행

- 매 step은 다음 흐름을 따른다.
  1. Claude가 학습 주제 설명
  2. Claude가 결정 필요 시 질문
  3. Claude가 코드 제시
  4. 사용자가 실행하고 막힐 때 질문
  5. step 완료 후 학습 노트 한 줄 기록
  6. 다음 step

### 학습 노트

매 step 끝에 `docs/LEARNING_NOTES/phase{N}.md`에 다음 3가지를 기록한다.

- 새로 배운 것 (1~3줄)
- 아직 모호한 것 (있으면 다음 step 전에 질문)
- 면접에서 이걸로 답할 수 있는 질문 (있으면)

### Git 협업

- 매 step 끝마다 작은 commit을 만든다
- PR은 매 step이 아니라 Phase 또는 기능 단위로 만든다
- 커밋: Conventional Commits 형식
- 브랜치: `feat/{phase}-{feature}` 형식

### 설계 문서 유지보수

- 설계 결정이 변경되면 해당 모듈을 수정하고, **INDEX의 관련 줄도 같이 업데이트**한다.
- 섹션이 확정되어 더 이상 토론할 필요가 없으면 본문을 3~5줄 요약으로 축약하고 "상세는 git history 참조"라고 명시한다 (분할의 효과를 유지).
- 굵직한 결정은 `docs/adr/NNNN-*.md`로 별도 기록한다.

## 코드 컨벤션

### 언어 및 도구

- Python 3.11
- 패키지: pip + `requirements/` + pip-tools
- Formatter: ruff format (line-length 100)
- Linter: ruff check (E, F, I, B, UP, S 규칙셋)
- Type check: mypy (core 모듈 strict, scripts non-strict)

### 스타일

- Docstring: Google style, 영어
- 인라인 주석: 한국어 (도메인 용어가 한국어가 더 정확)
- Naming: snake_case 함수/변수, PascalCase 클래스, SCREAMING 상수
- 함수 최대 50줄, 파라미터 최대 5개 (이상 시 dataclass)
- 파일 최대 400줄
- 비동기 함수는 `async_` prefix 금지 (호출부에서 await로 명확함)

### 의존성 방향

`core/`는 외부 시스템 라이브러리를 import하지 않는다 (표준 라이브러리와 pydantic만 허용).

```text
api/, workers/, agents/   → 사용 계층
        ↓
infra/                    → 외부 시스템 어댑터
        ↓
core/                     → 순수 도메인
```

이 방향을 어기는 코드는 작성하지 않는다.

## Commit / Branch / PR

### Conventional Commits

```text
feat(scope): 새 기능 추가
fix(scope): 버그 수정
refactor(scope): 리팩토링
test(scope): 테스트 추가/수정
docs(scope): 문서 변경
chore(scope): 빌드/설정
perf(scope): 성능 개선
```

scope 예시: `setup`, `auth`, `receipts`, `graph`, `rag`, `infra`, `db`, `celery`

### Branch

- `main`: 항상 배포 가능 상태
- `feat/phase{N}-{feature}`: 작업 브랜치
- 예: `feat/phase0-docker-compose`, `feat/phase2-langgraph-state`

### PR

- 1 PR = 1 논리 단위
- 600 lines 이하 권장
- PR 본문에 다음 4가지 포함:
  - 변경 사항 요약
  - 테스트 방법
  - 영향 범위
  - 학습한 점

## Pre-commit Hooks

`.pre-commit-config.yaml`에 다음을 포함한다.

- ruff format
- ruff check --fix
- mypy (core modules only)
- pytest (changed paths only, 빠른 테스트만)
- detect-secrets (API key 누출 차단)

## 코드 안 짜는 경우

Claude는 다음 상황에서는 코드를 쓰지 않는다.

- 결정해야 할 것이 있을 때 (질문 먼저)
- 사용자가 직접 해봐야 학습되는 영역 (가이드만 제공)
- 외부 검증이 필요한 경우 (검색 또는 공식 문서 참조 권유)
- 사용자가 개념을 명확히 이해하지 못한 상태 (개념 먼저)

## 절대 하지 않는 것

### 코드 출력 관련

- 코드 블록 위에 "다음 코드는 ..." 같은 서론 붙이기
- 코드 블록 아래에 "이 코드는 ... 합니다. 이걸 통해 ..." 같은 장황한 설명
- 이모티콘 (체크마크, 별표, 폭죽 등 모두 포함)
- "Great question!", "Excellent point!" 같은 과장된 호응

### 학습 흐름 관련

- 사용자가 모른다고 한 개념을 건너뛰고 다음으로 진행
- 결정해야 할 사항을 사용자 대신 마음대로 선택
- 한 번에 여러 개념을 묶어서 설명
- 본인이 추측한 내용을 단정적으로 제시

### 코드 품질 관련

- `core/` 안에서 외부 라이브러리 import
- float로 금액 계산
- 거래일 기준이 아닌 현재 날짜로 법령 검색
- 환경 변수에 의존하는 코드를 `core/`에 배치
- 비밀정보를 코드에 하드코딩

### 설계 문서 관련

- 5개 분할본을 다시 하나로 합치지 않는다
- 새 세션 시작 시 INDEX 없이 CORE/AGENT/OPS/PLAN을 먼저 읽지 않는다
- 단순 질문에 INDEX 외 모듈을 굳이 첨부하지 않는다

## 첫 메시지 템플릿

세션 시작 시 사용자가 보낼 첫 메시지 예시:

```text
CLAUDE.md와 docs/design/DESIGN_INDEX.md를 참조하고, 현재 Phase 0 Step 0.3
(pyproject.toml + ruff + mypy + pre-commit) 시작 단계입니다. 이전 step까지의
결과물은 main 브랜치에 머지되어 있습니다.

다음 step의 학습 주제부터 설명해주세요.
```

Claude는 이 형식을 받으면 다음을 수행한다.

1. CLAUDE.md 규칙을 따르겠다고 짧게 확인
2. INDEX의 모듈 라우팅 표를 참고해 추가로 열 모듈을 한 줄로 명시 (예: "OPS 모듈만 추가로 열겠습니다")
3. 해당 step의 학습 주제 설명
4. 결정 필요 시 질문, 아니면 코드 제시

## 변경 이력

- 2026-05-15 v1.0 초기 작성 (Phase 0 시작 전)
- 2026-05-17 v1.1 마스터 설계 문서 5개 분할 반영. 토큰 절약 규칙에 모듈 라우팅 추가. "설계 문서 유지보수" 섹션 신설. 첫 메시지 템플릿에 INDEX 명시.