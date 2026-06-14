# 반복 업무 자동화 5종 (분개·규칙학습·삼중대사·누락증빙·월마감)

세무사의 매달 반복 노동을 직접 줄이는 기능 묶음. 모두 백엔드(도메인 + API +
마이그레이션 + 테스트)로 구현됨. 브랜치: `feat/journal-export`.

설계 원칙: 핵심 판단 로직은 `core/`의 순수 함수(외부 라이브러리 없음, 단위
테스트 100%)로 두고, API/worker는 그 함수를 호출만 한다.

---

## F1. 분개(전표) 자동 생성 + 회계프로그램 import CSV

승인 영수증·세금계산서를 복식부기 차/대변 전표로 변환해, 더존·세무사랑이 그대로
읽는 범용 일반전표 CSV(UTF-8 BOM)로 내보낸다. "다시 입력" 단계를 없앤다.

- 도메인: `core/tax/journal.py` (매입 공제/불공제·매출 전표, 차대변 균형 불변식),
  `core/tax/journal_export.py`
- API: `GET /api/v1/journal/entries` (미리보기), `GET /api/v1/journal/export.csv`
- 분개 규칙: 공제 매입 → 차)비용+부가세대급금 / 대)결제계정; 불공제 → 부가세를
  비용 산입; 매출 → 차)외상매출금 / 대)매출+부가세예수금

## F2. 반복 거래 자동 학습(거래처별 계정과목 규칙)

가맹점→계정과목을 한 번 정하면 다음부터 자동 적용. 키워드 분류기보다 우선.

- 도메인: `core/tax/account_rules.py` (완전일치 > 부분포함 우선순위)
- 모델: `AccountRule` (테넌트 전역 또는 고객사별, `hit_count` 효용 추적), 마이그 0010
- API: `GET/POST/DELETE /api/v1/account-rules`, `POST .../learn-from-receipt`
- 적용 지점: worker가 키워드 분류 후 학습 규칙으로 override + hit_count 증가

## F3. 통장 거래내역 + 삼중 대사(통장 ↔ 카드 ↔ 세금계산서)

통장 입출금을 카드·세금계산서에서 도출한 예상 현금흐름과 금액·거래일로 매칭해,
"근거 없는 입출금"과 "통장 미반영" 항목만 남긴다.

- 도메인: `core/tax/reconciliation.py` (그리디 1:1 매칭), `core/bank.py` (범용 통장 CSV 파서)
- 모델: `BankTransaction`, 마이그 0011
- API: `POST /api/v1/bank/upload`, `GET /bank/transactions`,
  `GET /bank/reconciliation`, `POST /bank/reconciliation/apply`

## F4. 누락 증빙 감지 + 고객 요청 문구

카드 결제 중 대응 영수증이 없는 건을 가려내고, 고객에게 그대로 보낼 요청 문구까지
생성한다.

- 도메인: `core/tax/missing_evidence.py` (카드↔영수증 1:1 매칭)
- API: `GET /api/v1/missing-evidence` (누락 목록 + 합계 + request_message)

## F5. 고객사별 월마감 체크리스트

매달 반복되는 마감 절차(자료수집→검토→분류→대사→누락증빙→집계→분개→신고)를
표준 8단계 템플릿으로 만들고 진행률을 추적한다.

- 도메인: `core/tax/monthly_closing.py` (단계 템플릿·진행률·상태)
- 모델: `MonthlyClosing` (고객사×연×월, steps JSON), 마이그 0012
- API: `POST /api/v1/monthly-closings` (멱등), `GET` 목록/단건,
  `PATCH .../steps/{step_key}` (단계 토글)

---

## 테스트

신규 순수 도메인 테스트: journal 12, account_rules 6, reconciliation 10,
missing_evidence 5, monthly_closing 5. 전체 스위트 233개 통과.

## 남은 작업(후속)

- 프론트엔드 화면 (현재 백엔드 API만). 분개 미리보기/내보내기, 대사 보드,
  누락 증빙 목록, 월마감 체크리스트 UI는 미구현.
- 마이그레이션 0010~0012는 모델과 1:1로 작성했으나 실제 DB에 `alembic upgrade`로
  적용 검증은 하지 않음(로컬 DB 미기동). 테스트는 모델 메타데이터 기반으로 통과.
- F3 삼중대사는 금액·거래일 정확매칭 기반. 카드 합산 결제(월 카드대금 1건 = 다건
  합계) 매칭, 부분 금액 매칭은 후속 고도화 대상.
- F2 규칙은 영수증 worker에만 연결. 카드내역 ingest에도 동일 적용은 후속.
