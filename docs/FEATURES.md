# Tax-Copilot 전체 기능 맵

세무사를 위한 AI 코파일럿의 기능 현황과 로드맵.
"구현 완료 → 단기 필수 → 중기 실용 → 장기 고도화" 순으로 정리한다.

> **면책 고지**: 본 시스템의 모든 분석 결과는 세무사의 업무를 보조하는 참고 자료이며,
> 최종 세무 판단의 책임은 담당 세무사에게 있습니다.

---

## 1. 현재 구현된 기능 (MVP — Phase 0~6 완료)

### 1.1 인프라 & 인증

| 기능 | 설명 | 파일 |
|------|------|------|
| JWT 인증 | access token 발급, 8시간 유효, 필수 클레임 검증 | `auth/jwt.py` |
| 역할 기반 접근 제어 | `admin / staff / client` 3단계 권한 분리 | `auth/permissions.py` |
| bcrypt 비밀번호 해싱 | 72바이트 초과 가드 포함 | `auth/password.py` |
| 멀티테넌시 | `tenant_id` 기반 데이터 격리 | DB 모델 전반 |
| pydantic-settings 설정 관리 | `.env` 로드, 프로덕션 불안전 기본값 차단 | `core/config.py` |
| structlog JSON 로깅 | request_id contextvar, PII 마스킹 (사업자번호·카드번호) | `core/logging.py` |
| 감사 로그 | 모든 상태 전이를 `audit_events` 테이블에 기록 | `audit/events.py` |

### 1.2 영수증 업로드 & 저장

| 기능 | 설명 | 파일 |
|------|------|------|
| 파일 업로드 | JPG·PNG·PDF 지원, magic bytes 검증 | `api/v1/receipts.py` |
| 확장자·MIME 검증 | 화이트리스트 + 내용 기반 이중 검증 | `core/receipts/validation.py` |
| SHA-256 중복 감지 | `(tenant_id, file_hash)` unique 제약으로 동일 파일 재처리 방지 | `core/receipts/validation.py` |
| 로컬 스토리지 | `./uploads/receipts/{tenant_id}/{hash[:2]}/{hash}.{ext}` | `infra/storage/local.py` |
| 경로 순회 방지 | `storage_root` 외부 경로 접근 차단 | `infra/storage/local.py` |
| 영수증 목록 조회 | 상태 필터, 페이지네이션 | `api/v1/receipts.py` |

### 1.3 AI 워크플로우 (LangGraph)

| 기능 | 설명 | 파일 |
|------|------|------|
| 이미지 품질 검사 | Pillow 기반 해상도·손상 여부 판단, unreadable 시 즉시 HITL | `agents/nodes/image_quality.py` |
| Vision 필드 추출 | Gemini Vision structured output → `ParsedReceipt` | `infra/gemini/vision.py` |
| 거래일 기준 법령 검색 | `effective_from <= as_of_date < effective_to` Qdrant Range 필터 | `rag/search.py` |
| 결정론적 세액 계산 | LLM 계산 금지, Python `Decimal` 정수 원 단위 | `agents/nodes/calculation.py` |
| 판단 초안 생성 | `evidence_type` + 법령 근거 기반 `vat_creditable` + `risk_flags` | `agents/nodes/audit_prepare.py` |
| HITL interrupt/resume | `human_review_node`에서 interrupt, `Command(resume=...)` 재개 | `agents/nodes/human_review.py` |
| PostgreSQL Checkpointer | LangGraph 상태를 DB에 저장, worker 재시작 후 resume 가능 | `api/main.py` (lifespan) |

### 1.4 비동기 처리 (Celery)

| 기능 | 설명 | 파일 |
|------|------|------|
| Celery 태스크 dispatch | 업로드 즉시 큐잉, 동기 응답 반환 | `workers/tasks/receipts.py` |
| Redis NX 분산 락 | `(tenant_id, file_hash)` 기준 동시 처리 방지 | `infra/cache/redis_lock.py` |
| Idempotency 3중 보장 | acks_late + Redis lock + DB 상태 체크 | `workers/tasks/receipts.py` |
| 락 자동 해제 | 태스크 완료·실패 시 `finally`로 락 반환 | `workers/tasks/receipts.py` |
| 터미널 상태 재처리 방지 | `APPROVED / REJECTED / FAILED / NEEDS_REVIEW` 모두 가드 | `workers/tasks/receipts.py` |

### 1.5 검토 API

| 기능 | 설명 | 파일 |
|------|------|------|
| 검토 대기 목록 | `NEEDS_REVIEW` 상태 영수증 조회 | `api/v1/reviews.py` |
| 승인 / 반려 | `approved: bool + comment` 로 LangGraph resume | `api/v1/reviews.py` |
| 검토 이력 조회 | 완료된 영수증 목록 | `api/v1/reviews.py` |
| ExternalServiceError 503 | Gemini·Qdrant 장애 시 올바른 HTTP 503 반환 | `api/errors.py` |

### 1.6 프론트엔드 (Next.js)

| 기능 | 설명 | 경로 |
|------|------|------|
| 로그인 페이지 | JWT 발급, 세션 저장 | `frontend/app/login/` |
| 영수증 업로드 페이지 | 드래그 앤 드롭, 업로드 상태 표시 | `frontend/app/page.tsx` |
| 검토 화면 | NEEDS_REVIEW 목록 + 승인/반려 버튼 | `frontend/app/` |

### 1.7 배포 & 운영

| 기능 | 설명 | 파일 |
|------|------|------|
| Dockerfile | multi-stage 빌드 | `Dockerfile` |
| render.yaml | API 서버 + Celery worker 분리 배포 | `render.yaml` |
| GitHub Actions CI | lint → mypy → pytest on push | `.github/workflows/ci.yml` |
| Alembic 마이그레이션 | DB 스키마 버전 관리 | `alembic/versions/` |

---

## 2. 단기 필수 기능 (서비스 실제 작동에 필요)

현재 구현은 "영수증 1장 판단" 파이프라인이다.
실제 세무사가 쓰려면 아래 기능이 없으면 실무에 사용할 수 없다.

### 2.1 부가세 신고서 집계 ⭐ 최우선

**없으면 안 되는 이유**: 세무사가 필요한 건 개별 판단이 아니라 _한 달 치 영수증의 매입세액 합계_ 다.
현재는 영수증을 하나씩 처리하지만 부가세 신고에는 공급가액·세액 합산 테이블이 필요하다.

- [x] 기간별(월/분기) 영수증 집계 API — `GET /api/v1/vat/summary?client_company_id&from_date&to_date`
- [x] 매입세액공제 대상 합계 / 불공제 합계 분리 — `creditable` / `non_creditable` 필드
- [x] 계정과목별 집계 — `by_account_code` 목록
- [ ] 부가세 신고서 초안 생성 (JSON → PDF export)
- [ ] 신고 기간 슬롯 관리 (1기 예정/확정, 2기 예정/확정)

### 2.2 고객사 포털 (역할 분리)

**없으면 안 되는 이유**: 현재 세무사(staff)가 직접 업로드하는 구조다.
실제로는 _고객 기업이 영수증을 올리고, 세무사는 검토만_ 한다.

- [ ] `client` 역할 사용자가 영수증 직접 업로드
- [ ] 고객사별 대시보드 (업로드 현황, 처리 상태)
- [ ] 세무사 ↔ 고객사 메모/코멘트 스레드
- [ ] 고객사 초대 이메일 (신규 계정 생성 플로우)

### 2.3 신고 기한 관리

**없으면 안 되는 이유**: 기한 초과 시 가산세가 발생한다.
세무사가 담당 고객사별로 기한을 별도 관리해야 한다면 이 서비스의 가치가 낮아진다.

- [ ] 부가세(1월·7월), 종합소득세(5월), 법인세(3월) 자동 등록
- [ ] 고객사별 마감 캘린더
- [ ] D-7, D-1 이메일/슬랙 알림
- [ ] 신고 완료 체크 및 이력 저장

### 2.4 세금계산서 진위 확인

**없으면 안 되는 이유**: 이미지만 보고 판단하면 위조 세금계산서를 잡을 수 없다.

- [ ] 국세청 홈택스 전자세금계산서 API 연동
- [ ] 사업자등록번호 유효성 검증 (국세청 API)
- [ ] 추출된 금액 vs 홈택스 데이터 교차 검증
- [ ] 불일치 시 자동 HITL 이관

---

## 3. 중기 실용 기능 (실용성 크게 향상)

### 3.1 경비 계정과목 자동 분류 ⭐ 포트폴리오 임팩트 高

**왜 중요한가**: 영수증 → 회계 프로그램(더존·세무사랑) 연동에 필수다.
계정과목이 없으면 이 시스템의 출력이 회계 처리로 이어지지 않는다.

- [x] 계정과목 스키마 정의 (복리후생비·접대비·소모품비·여비교통비·통신비 등 15종)
- [x] audit_prepare 노드에 계정과목 분류 추가 (rule-based, 키워드 + 증빙 종류)
- [x] 세무사 수정 확정 PATCH API (`PATCH /v1/receipts/{id}/account-code`)
- [ ] 업무용/비업무용 분리 (다음 Sprint)
- [ ] 회계 프로그램 export 형식 (다음 Sprint)

### 3.2 의미 기반 중복 영수증 감지

**왜 중요한가**: 현재 `file_hash` 기반이라 같은 영수증을 다시 촬영하면 중복을 못 잡는다.
동일 거래의 이중 처리는 세액 계산 오류로 이어진다.

- [x] (가맹점명 + 금액) 조합 유사도 검사 — `rapidfuzz.fuzz.partial_ratio >= 80` + 금액 동일
- [x] 동일 거래 의심 시 `duplicate_suspect=True` + `duplicate_receipt_ids` API 응답에 포함
- [ ] 중복 의심 영수증 쌍 시각화 (프론트엔드)

### 3.3 법령 자동 업데이트

**왜 중요한가**: 법이 개정되면 corpus를 수동으로 갱신해야 한다.
자동화하지 않으면 잘못된 법령으로 판단하는 리스크가 생긴다.

- [ ] 법제처 API 주기적 폴링 (GitHub Actions 스케줄 또는 Celery beat)
- [ ] 개정 감지 → chunk diff 생성 → 재임베딩
- [ ] 기존 판단에 영향 주는 개정 발생 시 세무사 알림
- [ ] corpus version 자동 증가 및 이력 관리

### 3.4 실시간 처리 상태 알림

**왜 중요한가**: 현재 클라이언트가 처리 완료를 알려면 폴링해야 한다.

- [ ] SSE(Server-Sent Events) 엔드포인트: 처리 상태 스트리밍
- [ ] 처리 완료 시 이메일 또는 슬랙 알림
- [ ] 프론트엔드 실시간 상태 업데이트 (폴링 제거)

### 3.5 영수증 일괄 업로드

**왜 중요한가**: 실제 세무사는 한 달치 영수증 수십 장을 한 번에 처리해야 한다.

- [ ] ZIP 파일 업로드 → 자동 압축 해제 → 병렬 처리
- [ ] 일괄 업로드 진행률 표시
- [ ] 처리 실패 항목 재시도 UI

---

## 4. 차별화 기능 (포트폴리오·실제 서비스 모두에서 강점)

### 4.1 세무조사 리스크 스코어링

**왜 중요한가**: 세무사가 가장 필요로 하는 인사이트 중 하나다.
기술적으로도 흥미롭고 면접에서 설명하기 좋다.

- [x] 접대비 비율, 간이영수증 비율, 위험플래그 비율, 중복 비율 지표 계산
- [x] 고객사별 리스크 점수 0~100 산출 — `GET /api/v1/risk/score`
- [x] 설명 생성 — `"세무조사 리스크가 높습니다. 접대비 비율 40% ..."` 형태
- [ ] 업종별 평균과 비교 (이상치 탐지) — 외부 벤치마크 데이터 필요
- [ ] 리스크 트렌드 차트 (월별 변화) — 프론트엔드

### 4.2 판단 근거 추적성 (Explainability)

**왜 중요한가**: AI가 왜 이 판단을 했는지 세무사가 납득해야 검토 품질이 올라간다.
감사 시에도 근거 문서가 필요하다.

- [ ] 각 판단에 사용된 법령 조문 직접 링크
- [ ] 과거 동일 유형 영수증의 처리 이력과 비교
- [ ] "이전에는 이렇게 판단했는데 이번에 달라진 이유" 설명
- [ ] 판단 근거 PDF export (감사 대비 문서)

### 4.3 세무사-AI 피드백 루프

**왜 중요한가**: 세무사가 번복한 판단이 쌓이면 AI를 고도화할 수 있다.
지속적으로 좋아지는 시스템은 포트폴리오에서 강력한 차별점이다.

- [ ] 승인/반려 결정 + 코멘트를 학습 데이터로 저장
- [ ] 자주 번복되는 패턴 분석 리포트
- [ ] Few-shot 예시 자동 갱신 (프롬프트 개선 파이프라인)
- [ ] RAGAS 기반 RAG 품질 정량 평가 지표

---

## 5. 장기 고도화 (안정화 후 단계적 추가)

### 5.1 비용 최적화

- [ ] Semantic Cache: 유사 질의 재사용 (Redis vector index)
- [ ] Prompt Cache: Anthropic/Gemini 캐시 토큰 활용
- [ ] 배치 임베딩: corpus 업데이트 시 batch API 사용
- [ ] 모델 라우팅: 단순 케이스 → 소형 모델, 복잡 케이스 → 대형 모델
- [ ] 테넌트별 LLM 호출 예산 제한

### 5.2 운영 안정성

- [ ] Circuit Breaker: Gemini·Qdrant 연속 실패 시 자동 HITL 전환
- [ ] Dead Letter Queue: 처리 불가 태스크 별도 보관 및 재시도 UI
- [ ] OpenTelemetry 분산 추적: API → Celery → LangGraph 전 구간
- [ ] Celery Flower 또는 대체 모니터링 대시보드
- [ ] Graceful Degradation 자동 테스트 (chaos engineering)

### 5.3 보안 고도화

- [ ] 악성코드 스캔: 업로드 파일 ClamAV 검사
- [ ] 필드 레벨 암호화: 사업자번호·계좌번호 DB 저장 시 암호화
- [ ] 감사 로그 불변 export: S3/R2에 서명된 로그 저장
- [ ] 테넌트별 데이터 완전 삭제 (GDPR 대응)
- [ ] Redis sliding window rate limiter (테넌트별 API 호출 제한)
- [ ] 오브젝트 스토리지 생명주기: 5년 보존 후 자동 삭제

### 5.4 외부 시스템 연동

- [ ] Cloudflare R2 스토리지 어댑터 (현재 로컬 스토리지 교체)
- [ ] 회계 프로그램 연동: 더존 Smart A, 세무사랑 CSV import 포맷
- [ ] 슬랙 알림: 검토 요청, 기한 임박
- [ ] 홈택스 전자신고 보조 (조회만, 신고 직접 전송은 제외)
- [ ] 국세청 사업자등록번호 진위 확인 API

### 5.5 비즈니스 인텔리전스

- [ ] 테넌트별 KPI 대시보드: AI 자동 처리율, HITL 이관율, 번복률
- [ ] 세무사 생산성 지표: 월평균 처리 영수증 수, 평균 검토 시간
- [ ] 고객사별 비용 분석: 영수증당 평균 처리 비용
- [ ] 업종별 벤치마크 리포트

---

## 6. 의도적으로 제외하는 기능

| 기능 | 제외 이유 |
|------|-----------|
| AI 세무신고 직접 제출 | 세무사법 위반 리스크. 세무신고 대리는 세무사 자격 필수 |
| LLM 세액 계산 | float 오차 → 실제 금전 리스크. Python Decimal 사용 원칙 불변 |
| 개인 납세자 직접 서비스 | B2B(세무사 사무소) 타깃. 개인 대상은 별도 법적 검토 필요 |
| 실시간 홈택스 신고 전송 | 보안·책임 이슈. 조회만 허용 |
| 전체 서비스 기준 file_hash unique | 테넌트 간 파일 존재 여부 노출 리스크. `(tenant_id, file_hash)` 유지 |

---

## 7. 우선순위 요약

```
즉시 가능 (기술 난이도 낮음, 임팩트 高)
├── 경비 계정과목 분류          ← LLM 스키마 추가, 회계 프로그램 연동 가능
└── 의미 기반 중복 감지         ← 데이터 정합성 직접 영향

단기 필수 (서비스 실제 사용에 필요)
├── 고객사 포털 (역할 분리)     ← 현재 역할 구조가 역방향
├── 부가세 집계 API             ← 없으면 신고 업무에 쓸 수 없음
└── 신고 기한 알림              ← 가산세 방지, 세무사 직접 요청 사항

중기 차별화 (포트폴리오 + 실서비스 모두)
├── 세무조사 리스크 스코어링    ← 면접 설명하기 좋음, 세무사 수요 높음
├── 법령 자동 업데이트          ← RAG 품질 유지에 필수
└── 판단 근거 추적성            ← 감사 대비, explainability
```

---

*최종 수정: 2026-05-24 | 관련 문서: `DESIGN_INDEX.md`, `DESIGN_PLAN.md`*
