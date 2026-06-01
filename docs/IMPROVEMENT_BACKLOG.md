# 개선 백로그 (프론트 디자인 작업 중 발견)

> 작성일: 2026-06-01
> 맥락: 프론트엔드 전면 리디자인("모던 핀테크 Trust") 작업을 하며 코드 전반을 보던 중 발견한, 추가/수정하면 좋을 항목 모음. 우선순위·근거·관련 파일·예상 난이도 포함.

---

## 0. 이번에 완료된 것 (참고용)

- **디자인 시스템 전면 교체** — `frontend/app/globals.css`(토큰/컴포넌트 클래스), Pretendard 폰트(@import), 인디고/에메랄드/로즈 시맨틱.
- **공유 컴포넌트** — `components/Sidebar.tsx`(SVG 아이콘), `components/StatCard.tsx`(아이콘 칩+hero), `components/Charts.tsx`(무의존성 SVG 도넛/막대).
- **깊이·모션** — 그리드 배경, 버튼 그라데이션, KPI 스트립, 연결형 스테퍼, 진입 애니메이션.
- **영수증 실제 미리보기** — 백엔드 `GET /api/v1/receipts/{id}/file` 신설 + 프론트 `fetchReceiptFile()`로 이미지/PDF 렌더.
- **reports 차트**, **tax-invoices 표시필터(전체/매입/매출)**, **인라인 색상 토큰화**.
- **커밋 막던 mypy 이슈 해결** — pre-commit에 `sqlalchemy` 추가 + JSON 컬럼 타입 파라미터 보강.

### ⚠️ 마무리 정리거리
- `frontend/app/preview/page.tsx` — 시각 확인용 **임시 페이지. 삭제 예정.**
- (참고) 헤드리스 스크린샷은 WSL에 시스템 라이브러리가 없어, deb를 로컬에 풀어 `LD_LIBRARY_PATH`로 우회해서 캡처함.
- (교훈) App Router `layout.tsx`에 **수동 `<head>` 금지** — globals.css 주입이 깨져 dev가 빈 CSS를 서빙함. 폰트는 globals.css `@import`로 로드 중.

---

## 1. 🔴 기능 공백 — 백엔드 API는 있는데 프론트 화면이 없음 (가성비 최상)

백엔드 라우터(`src/tax_copilot/api/v1/`): `auth, deadlines, monthly_reports, portal, receipts, reviews, risk, tax_invoices, vat`
프론트 페이지(`frontend/app/`): `login, page(검토), history, tax-invoices, reports` → **deadlines / risk / vat / portal 화면 없음**

| # | 항목 | 무엇 / 왜 | 관련 파일 | 난이도 |
|---|------|-----------|-----------|--------|
| 1 | **신고 기한 관리** | 부가세·원천세 신고 D-day, 캘린더/타임라인. 세무 서비스의 핵심인데 현재 reports에 "다음 기한" 한 줄만. | `api/v1/deadlines.py` (백엔드 존재), 신규 `frontend/app/deadlines/` | 중 |
| 2 | **리스크 대시보드** | 영수증별 risk_flags는 있으나 **고객사 전체 위험 집계** 화면 없음. 검토필요/중복의심/한도초과 한눈에. | `api/v1/risk.py`, 신규 `frontend/app/risk/` | 중 |
| 3 | **부가세 신고 준비** | 매입·매출 집계를 신고서 형태로. | `api/v1/vat.py`, 신규 `frontend/app/vat/` | 중 |
| 4 | **고객 포털** | client 역할 사용자가 자기 회사 영수증/리포트만 보는 뷰. 설계 초안만 있고 미구현. | `api/v1/portal.py`, `docs/superpowers/specs/2026-05-25-client-portal-design.md` | 상 |

---

## 2. 🟡 UX / 플로우

| # | 항목 | 무엇 / 왜 | 관련 파일 | 난이도 |
|---|------|-----------|-----------|--------|
| 5 | **실시간 업데이트(SSE)** | 현재 5초 **폴링**(`setTimeout(fetchReviews, 5000)`). 백엔드에 이미 SSE `/receipts/{id}/events` 있음 → 즉시 갱신 + 부하↓. | `frontend/app/page.tsx:118`, `api/v1/receipts.py` events 엔드포인트 | 중 |
| 6 | **워크플로우 스테퍼 실제 연동** | 지금 `activeStage = selected ? 3 : 0`로 고정(가짜). 실제 상태(PENDING→PROCESSING→NEEDS_REVIEW→완료) 반영 필요. | `frontend/app/page.tsx` | 하 |
| 7 | **검색/필터/페이지네이션** | history·tax-invoices가 전체(limit=100) 일괄 로드. 상태·기간·거래처 필터 + 페이지네이션. | `frontend/app/history/`, `tax-invoices/`, `lib/api.ts` | 중 |
| 8 | **중복 의심 강조** | 모델에 `duplicate_suspect`/`duplicate_receipt_ids` 있으나 UI 노출 약함. 검토 화면에 경고 배지. | `frontend/app/page.tsx`, `infra/db/models/receipt.py` | 하 |

---

## 3. 🟢 디자인 / 완성도

| # | 항목 | 무엇 / 왜 | 난이도 |
|---|------|-----------|--------|
| 9  | **토스트 알림** | 업로드 성공/실패가 인라인 텍스트 → 우상단 토스트로 통일. | 하 |
| 10 | **모달 키보드 지원** | Esc 닫기·포커스 트랩 없음(접근성). | 하 |
| 11 | **스켈레톤 로딩** | 테이블/카드에 스피너 대신 스켈레톤. | 하 |
| 12 | **상단 사용자 영역** | 로그인 사용자/역할/회사 표시 없음. 토픽바에 프로필 칩. | 하 |

---

## 4. 🔧 기술 / 보안

| # | 항목 | 무엇 / 왜 | 관련 파일 | 난이도 |
|---|------|-----------|-----------|--------|
| 13 | **기본 관리자 비밀번호** | `changeme` placeholder. 배포 전 환경변수화/강제 변경. **보안 중요.** | `scripts/seed_admin.py:21` | 하 |
| 14 | **파일 서빙 접근권한 테스트** | 신설 `/receipts/{id}/file`에 권한 테스트 없음(민감). client 격리 검증 테스트 추가. | `tests/test_receipt_ops.py` 참고 | 하 |
| 15 | **mypy 커버리지 확대** | pre-commit이 `^src/tax_copilot/core/`만 검사 → api/infra에 latent 타입 에러 존재(4건 확인). | `.pre-commit-config.yaml` | 중 |
| 16 | **포맷터 중복 제거** | `money()`/날짜 포맷이 페이지마다 복붙 → `frontend/lib/format.ts`로 일원화. | 프론트 전반 | 하 |

---

## 추천 진행 순서

1. **신고 기한 관리 화면** (#1) — 백엔드 이미 있음, "세무 서비스다움" 임팩트 최대
2. **SSE 실시간화** (#5) — 폴링 제거, 즉시 갱신
3. **스테퍼 실제 상태 연동** (#6) — 빠르고 완성도↑
4. 이후 리스크/부가세 화면(#2,#3), 디자인 디테일(#9~12), 보안(#13,#14)

> 다음 세션에서 위 번호로 지정해 주시면 바로 착수합니다.
