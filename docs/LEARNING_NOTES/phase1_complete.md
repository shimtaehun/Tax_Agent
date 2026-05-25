# Phase 1 완료 기록

완료일: 2026-05-24
총 작업 내용: 인증, DB 모델, 파일 업로드, 감사 로그

---

## 구현된 것

### DB 모델 (infra/db/models/)
- `Tenant`: 세무사 사무소 단위
- `ClientCompany`: 고객사 (tenant 소속). 설계 리뷰에서 추가 확정
- `User`: 사용자 (tenant 소속, role: client/staff/admin)
- `Receipt`: 영수증. `client_company_id` 포함
- `AuditEvent`: 모든 상태 전이 이력

### Alembic migration
- `alembic/versions/0001_initial_core_schema.py`: 5개 테이블 + 인덱스 + unique constraint

### JWT 인증 (auth/)
- `password.py`: `bcrypt` 직접 사용 (passlib은 Python 3.12 + bcrypt 4.x 호환 문제)
- `jwt.py`: `python-jose`로 HS256 JWT 생성/검증
- `permissions.py`: `require_admin`, `require_staff_or_admin`

### API (api/)
- `deps.py`: JWT 검증 → CurrentUser dataclass 주입
- `api/v1/auth.py`: POST /api/v1/auth/login
- `api/v1/receipts.py`: POST /api/v1/receipts (업로드), GET /api/v1/receipts/{id} (상태 조회)

### 파일 검증 (core/receipts/validation.py)
- magic bytes로 실제 MIME 타입 판별 (Content-Type 헤더 신뢰 안 함)
- 확장자 ↔ 감지된 MIME 타입 일치 검사 (content-type spoofing 방지)
- SHA-256 파일 해시로 중복 업로드 방지

### 로컬 스토리지 (infra/storage/local.py)
- `receipts/{tenant_id}/{hash[:2]}/{hash}.{ext}` 경로 구조

### 감사 로그 (audit/events.py)
- `record_event()`: audit_events 테이블에 상태 전이 기록

### seed 스크립트
- `scripts/seed_admin.py`: 초기 tenant + 기본 고객사 + admin 사용자 생성

---

## 테스트

26개 단위 테스트 통과
- `test_validation.py`: 파일 검증 9개
- `test_auth.py`: 비밀번호·JWT·권한 17개
- `test_healthz.py`: /healthz 1개

---

## 핵심 학습 포인트

**tenant scope 강제**
모든 DB 쿼리에 `tenant_id` 조건을 추가해야 tenant 간 데이터 누출을 막을 수 있다.
`receipts.py`의 `get_receipt_status`에서 `Receipt.tenant_id == current_user.tenant_id` 확인.

**magic bytes vs Content-Type**
HTTP `Content-Type` 헤더는 클라이언트가 위조할 수 있다.
실제 파일 내용의 첫 몇 바이트(magic bytes)를 검사해야 진짜 형식을 알 수 있다.

**passlib + bcrypt 4.x 문제**
passlib의 `detect_wrap_bug`가 72바이트 초과 테스트 문자열을 bcrypt 4.x에 보내면 `ValueError` 발생.
`bcrypt` 라이브러리를 직접 사용하면 문제 없다.

**ClientCompany 추가 배경**
설계 리뷰에서 "tenant(세무사 사무소) 안에서 고객사별 영수증 분류가 필요"하다고 확인.
`receipts.client_company_id`는 NOT NULL (모든 영수증은 반드시 고객사에 소속).

---

## 다음: Phase 2 (LangGraph)
- AgentState 정의
- 노드 skeleton (mocked intake, retrieval, calculation, audit_prepare)
- HITL interrupt/resume 흐름
- PostgreSQL Checkpointer 연결
- 전체 workflow integration test
