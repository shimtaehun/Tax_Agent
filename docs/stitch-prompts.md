# Tax-Copilot — Stitch 디자인 프롬프트 모음

> Google Stitch로 프론트 디자인을 다시 만들기 위한 프롬프트 모음입니다.
> 각 항목은 **English (Stitch 입력용)** 과 **한글 (검토용)** 을 함께 담았습니다.
> Stitch에는 영어 프롬프트를 넣되, 화면 안에 들어갈 라벨은 한글 그대로 둡니다.

---

## 작성/사용 팁

Stitch는 막연한 한 줄보다 아래 6가지 축을 명시할 때 결과가 좋습니다.

1. **제품/사용자** — 누가 무슨 일을 하는 화면인가
2. **플랫폼** — Web app / desktop dashboard (모바일 아님 명시)
3. **화면 단위** — 한 프롬프트에 한 화면씩
4. **레이아웃 구조** — 사이드바, 그리드, 카드, 테이블 등
5. **비주얼 스타일** — 톤, 컬러 HEX, 폰트, 라운드/그림자 강도
6. **실제 콘텐츠(한글 라벨)** — 더미 영어 대신 진짜 메뉴/지표명

진행 순서:
1. **0. 스타일 고정** 프롬프트로 톤을 먼저 잡기 (컬러/사이드바만 다듬기)
2. 마음에 들면 **A → B → C → D** 순서로 `same style as before` 이어가기
3. 생성 후 미세 조정 ("승인 버튼 더 크게", "테이블 행 높이 줄여줘")
4. 완성되면 HTML/CSS 또는 Figma로 export → 기존 `globals.css` CSS 변수와 매핑

---

## 0. 스타일 / 디자인 시스템 고정 (제일 먼저)

### English (Stitch 입력용)

```
Design a web dashboard for "Tax-Copilot", a B2B SaaS for Korean
licensed tax accountants (세무사). It is a professional AI-assisted
receipt & tax-invoice review tool — accountants approve or reject
AI-generated tax judgments (human-in-the-loop).

Platform: desktop web app (not mobile). Language: Korean UI labels.

Visual style — "Modern Fintech Trust":
- Clean, calm, data-dense but uncluttered. Trustworthy and precise,
  like Linear / Stripe Dashboard / Toss for business.
- Light theme. Background #f5f7fb, white panels #ffffff.
- Primary brand color: indigo #4f46e5 (hover #4338ca).
- Semantic colors: success green #059669, danger/reject red #e11d48,
  warning amber #d97706, info blue #2563eb. Use soft tinted backgrounds
  for status chips.
- Text: near-black navy #0f1a33 for headings, slate gray for secondary.
- Typography: Pretendard (clean Korean sans-serif), clear hierarchy.
- Components: 12px rounded corners, subtle soft shadows, thin 1px
  light-gray borders #e7ebf3. Generous whitespace.
- Left vertical sidebar navigation, top header with page title + user menu.

Sidebar menu items (Korean):
영수증 검토 · 처리 완료 · 세금계산서 · 카드내역 · 월별 리포트

Keep it professional and minimal — no playful illustrations, no gradients
on text. This is a tool accountants use all day.
```

### 한글 (검토용)

"Tax-Copilot"이라는, 한국 세무사를 위한 B2B SaaS 웹 대시보드를 디자인해줘.
AI가 영수증·세금계산서를 검토하는 전문 도구이고, 세무사가 AI의 세무 판단을
승인하거나 반려하는 방식(휴먼 인 더 루프)이야.

- **플랫폼**: 데스크톱 웹 앱 (모바일 아님). UI 라벨은 한국어.
- **비주얼 스타일 — "Modern Fintech Trust"**:
  - 깔끔하고 차분하며 정보 밀도는 높지만 복잡하지 않게. 신뢰감 있고 정밀한 느낌
    (Linear / Stripe 대시보드 / 토스 비즈니스 느낌).
  - 라이트 테마. 배경 `#f5f7fb`, 패널 흰색 `#ffffff`.
  - 메인 브랜드 컬러: 인디고 `#4f46e5` (호버 `#4338ca`).
  - 의미 색상: 성공 초록 `#059669`, 반려/위험 빨강 `#e11d48`, 경고 앰버
    `#d97706`, 정보 파랑 `#2563eb`. 상태 칩은 연한 톤 배경 사용.
  - 텍스트: 제목은 짙은 네이비 `#0f1a33`, 보조 텍스트는 슬레이트 그레이.
  - 폰트: Pretendard (깔끔한 한글 산세리프), 위계 명확하게.
  - 컴포넌트: 모서리 둥글기 12px, 은은한 그림자, 1px 연회색 테두리 `#e7ebf3`,
    여백 넉넉하게.
  - 좌측 세로 사이드바 내비게이션, 상단 헤더에 페이지 제목 + 유저 메뉴.
- **사이드바 메뉴**: 영수증 검토 · 처리 완료 · 세금계산서 · 카드내역 · 월별 리포트
- 전문적이고 미니멀하게 — 장식용 일러스트, 텍스트 그라데이션 금지.
  세무사가 하루 종일 쓰는 업무 도구임.

---

## A. 메인 — 영수증 검토 (HITL 핵심 화면)

### English (Stitch 입력용)

```
Same style as before. Screen: "영수증 검토" (Receipt Review) — the main
human-in-the-loop screen.

Left: a scrollable list/queue of pending receipts with thumbnail, 상호명
(merchant), 금액 (amount), 날짜, and a status chip (검토 대기 / 처리중).

Right (main panel): the selected receipt detail in two columns —
- Left column: the receipt image preview.
- Right column: AI-extracted fields (상호명, 금액, 날짜, 증빙 종류) shown
  as editable fields, plus an "AI 세무 판단" card showing 부가세 공제 가능
  여부 and a risk flag (위험 신호) with reasoning, and cited 법령 조항
  (e.g. 부가가치세법 제XX조).
- Bottom: two prominent action buttons — green "승인" and red "반려".

Add a top summary bar with stat cards: 검토 대기 건수, 오늘 승인, 위험 신호.
Data-dense but scannable.
```

### 한글 (검토용)

앞과 같은 스타일. 화면: "영수증 검토" — 휴먼 인 더 루프 핵심 화면.

- **왼쪽**: 검토 대기 영수증 목록(스크롤). 각 항목에 썸네일, 상호명, 금액,
  날짜, 상태 칩(검토 대기 / 처리중).
- **오른쪽(메인 패널)**: 선택한 영수증 상세를 2열로 —
  - 왼쪽 열: 영수증 이미지 미리보기.
  - 오른쪽 열: AI가 추출한 항목(상호명, 금액, 날짜, 증빙 종류)을 수정 가능한
    입력 필드로. 그 아래 "AI 세무 판단" 카드에 부가세 공제 가능 여부, 위험
    신호(이유 포함), 인용 법령 조항(예: 부가가치세법 제XX조).
  - 하단: 눈에 띄는 액션 버튼 2개 — 초록 "승인", 빨강 "반려".
- 상단에 요약 스탯 카드: 검토 대기 건수, 오늘 승인, 위험 신호.
- 정보 밀도는 높되 한눈에 훑을 수 있게.

---

## B. 세금계산서 / 카드내역 (테이블 중심)

### English (Stitch 입력용)

```
Same style as before. Screen: "세금계산서" management.
A filterable data table: columns 거래일, 거래처, 공급가액, 세액, 합계,
유형(매입/매출), 상태. Add a date-range filter, 매입/매출 toggle, and a
search box at top. Each row has a status chip and a row action menu.
Above the table, show 3 KPI cards: 총 매입세액, 총 매출세액, 집계 기간.
Include pagination. Clean enterprise data-grid look.
```

### 한글 (검토용)

앞과 같은 스타일. 화면: "세금계산서" 관리.

- 필터 가능한 데이터 테이블: 컬럼은 거래일, 거래처, 공급가액, 세액, 합계,
  유형(매입/매출), 상태.
- 상단에 기간 필터, 매입/매출 토글, 검색창.
- 각 행에 상태 칩과 행 액션 메뉴.
- 테이블 위에 KPI 카드 3개: 총 매입세액, 총 매출세액, 집계 기간.
- 페이지네이션 포함. 깔끔한 엔터프라이즈 데이터 그리드 느낌.

> 참고: "카드내역" 화면도 같은 테이블 레이아웃을 재사용 — 컬럼만 사용일자,
> 가맹점, 승인금액, 카드, 분류 상태로 바꿔서 별도 생성하면 됩니다.

---

## C. 월별 리포트

### English (Stitch 입력용)

```
Same style as before. Screen: "월별 리포트" (monthly settlement report),
print-friendly. Top: month selector + 고객사 selector + "PDF 저장" button.
Show summary KPI cards (영수증 처리 건수, 승인율, 매입세액, 세무조사 리스크
점수 as a gauge/score). Below: a bar chart of monthly receipts by status
and a line chart of 매입세액 trend. Then a clean summary table. Calm,
report-like layout with lots of whitespace.
```

### 한글 (검토용)

앞과 같은 스타일. 화면: "월별 리포트" — 인쇄(PDF)에 적합한 정산 리포트.

- 상단: 월 선택 + 고객사 선택 + "PDF 저장" 버튼.
- 요약 KPI 카드: 영수증 처리 건수, 승인율, 매입세액, 세무조사 리스크 점수
  (게이지/점수 형태).
- 그 아래: 상태별 월간 영수증 막대 차트, 매입세액 추이 라인 차트.
- 이어서 깔끔한 요약 테이블.
- 차분하고 리포트다운 레이아웃, 여백 넉넉하게.

---

## D. 로그인

### English (Stitch 입력용)

```
Same style as before. A centered login screen for "Tax-Copilot".
Left side: brand panel with the 🧾 Tax-Copilot logo, tagline
"세무사를 위한 AI 영수증 검토 시스템", on a subtle indigo-tinted background.
Right side: a white card with email + password fields, indigo "로그인"
button, and a small note "세무사 전용". Minimal and trustworthy.
```

### 한글 (검토용)

앞과 같은 스타일. 가운데 정렬된 "Tax-Copilot" 로그인 화면.

- **왼쪽**: 브랜드 패널 — 🧾 Tax-Copilot 로고, 태그라인 "세무사를 위한 AI
  영수증 검토 시스템", 은은한 인디고 톤 배경.
- **오른쪽**: 흰색 카드 — 이메일 + 비밀번호 입력 필드, 인디고 "로그인" 버튼,
  작은 안내 문구 "세무사 전용".
- 미니멀하고 신뢰감 있게.

---

## 코드 이식 메모

기존 `frontend/app/globals.css`의 디자인 토큰과 프롬프트 컬러가 일치하도록
작성했습니다. Stitch 결과를 옮길 때 아래 변수에 매핑하세요.

| 용도 | CSS 변수 | 값 |
|------|----------|-----|
| 배경 | `--bg` | `#f5f7fb` |
| 패널 | `--panel` | `#ffffff` |
| 브랜드 | `--primary` | `#4f46e5` |
| 성공/승인 | `--success` | `#059669` |
| 위험/반려 | `--danger` | `#e11d48` |
| 경고 | `--warn` | `#d97706` |
| 테두리 | `--line` | `#e7ebf3` |
| 본문 텍스트 | `--ink` | `#0f1a33` |
