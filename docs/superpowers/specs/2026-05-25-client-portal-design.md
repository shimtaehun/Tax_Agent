# 고객사 포털 설계 (초안)

> 2026-05-25 — 브레인스토밍 중단, 이어서 작업 예정

---

## 구현 범위

3가지 기능을 독립 API 그룹으로 구현한다.

---

## 1. client 업로드

**현재 상태**
- `POST /api/v1/receipts/` 는 인증만 확인 (staff/admin 가정)
- `User` 모델에 `client_company_id` (nullable) 이미 존재
- `Receipt` 모델에 `client_company_id` FK 이미 존재

**변경 내용**
- `role=client` 사용자도 업로드 허용
- 업로드 시 `client_company_id`를 요청 본문 대신 JWT에서 자동 설정
  - 다른 회사 이름으로 올리는 것을 방지 (보안)

---

## 2. 고객사 대시보드 API

**엔드포인트**: `GET /api/v1/portal/dashboard`

**접근 권한**: `role=client` 전용 (staff는 별도 관리 화면 사용)

**응답 예시**
```json
{
  "client_company_id": 3,
  "total": 42,
  "by_status": {
    "PENDING": 5,
    "PROCESSING": 2,
    "NEEDS_REVIEW": 1,
    "APPROVED": 30,
    "REJECTED": 4
  },
  "recent_receipts": [ "...최근 5건..." ]
}
```

---

## 3. 영수증 코멘트

**DB 스키마**: 새 테이블 `receipt_comments`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | int PK | |
| receipt_id | FK → receipts | |
| author_id | FK → users | |
| body | text | 코멘트 내용 |
| created_at | timestamp | |

**스레드 구조**: 평탄 리스트 (답글 없음)

**API**
- `GET /api/v1/receipts/{id}/comments` — 목록 조회
  - 접근: staff/admin 전체, client는 자기 `client_company_id` 소속 영수증만
- `POST /api/v1/receipts/{id}/comments` — 코멘트 작성
  - 접근: 위와 동일

---

## 미결 사항

- 대시보드에서 보여줄 정보 범위 (현재 status 집계 + 최근 5건)
- 코멘트 권한 상세 확인 필요

---

## 기술 스택 참조

- 기존 패턴: `src/tax_copilot/api/v1/receipts.py`, `src/tax_copilot/api/v1/deadlines.py`
- DB 모델: `src/tax_copilot/infra/db/models/`
- 의존성 방향: `api/ → infra/ → core/` (core에 외부 라이브러리 import 금지)
