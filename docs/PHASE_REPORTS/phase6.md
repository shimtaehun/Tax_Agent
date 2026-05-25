# Phase 6 완료 보고서 — Next.js UI + 배포 + README

완료일: 2026-05-24

## 목표

포트폴리오 완성을 위한 마지막 단계.
- FastAPI에 CORS 미들웨어 추가 (프론트엔드 연동)
- Next.js UI를 실제 API와 연결 (로그인, 업로드, 승인/반려)
- `render.yaml`에 Celery worker 서비스 추가
- README 완성

---

## 구현한 컴포넌트

### FastAPI CORS (`src/tax_copilot/api/main.py`)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`settings.frontend_url`을 환경 변수로 받아 배포 환경(Render 등)에서 실제 프론트엔드 URL을 허용한다.

### API 클라이언트 (`frontend/lib/api.ts`)

브라우저 `localStorage`에서 JWT를 읽어 `Authorization: Bearer` 헤더로 추가한다. 401 응답 시 자동으로 로그인 페이지로 리다이렉트한다.

주요 함수:
- `login(email, password)` → JWT를 localStorage에 저장
- `getPendingReviews()` → `GET /api/v1/reviews/pending`
- `uploadReceipt(file)` → `POST /api/v1/receipts` (FormData)
- `decide(receiptId, approved, comment)` → `POST /api/v1/reviews/{id}/decide`

### 로그인 페이지 (`frontend/app/login/page.tsx`)

`"use client"` 컴포넌트. 이메일/비밀번호 폼 → `login()` API 호출 → 성공 시 `/`로 이동.

### 메인 대시보드 (`frontend/app/page.tsx`)

`"use client"` 컴포넌트. 마운트 시:
1. `isLoggedIn()` 체크 → 미로그인이면 `/login`으로 리다이렉트
2. `getPendingReviews()` 호출 → 사이드바에 대기 목록 표시
3. 영수증 선택 → 검토 패널에 상세 정보 + 승인/반려 버튼
4. 업로드 버튼 → `<input type="file" hidden>` 트리거 → `uploadReceipt()` 호출

### render.yaml 업데이트

Celery Worker 서비스 추가:
```yaml
- type: worker
  name: tax-copilot-celery
  env: docker
  dockerCommand: celery -A tax_copilot.workers.celery_app worker --loglevel=info --concurrency=2
```

---

## 설계 결정

### Server Component vs Client Component

Next.js App Router에서 기본은 Server Component다. 데이터 페칭을 서버에서 하면 초기 로드가 빠르지만, JWT 인증 체크와 상태 관리(`useState`, `useEffect`)가 필요한 이 페이지는 `"use client"`를 써야 한다.

### 파일 업로드 hidden input 패턴

```tsx
const fileRef = useRef<HTMLInputElement>(null);
// ...
<button onClick={() => fileRef.current?.click()}>업로드</button>
<input ref={fileRef} type="file" style={{ display: "none" }} onChange={handleUpload} />
```

`<input type="file">`의 기본 스타일을 완전히 숨기고, 커스텀 버튼으로 트리거한다. `onChange`에서 파일을 읽어 API에 FormData로 전송한다.

### CORS `allow_credentials=True`가 필요한 이유

`Authorization` 헤더가 포함된 요청(credentialed request)을 브라우저가 CORS preflight 없이 보내려면, 서버가 `Access-Control-Allow-Credentials: true`를 반환해야 한다. `allow_origins=["*"]`와는 함께 사용할 수 없고, 구체적인 origin을 명시해야 한다.

---

## 프론트엔드 빌드 결과

```
Route (app)              Size    First Load JS
┌ ○ /                  2.95 kB        105 kB
└ ○ /login             1.43 kB        104 kB
```

`npm run build` 성공. TypeScript 타입 오류 없음.

---

## 최종 상태

- 백엔드 테스트: 73개 전체 통과
- 프론트엔드 빌드: 성공 (타입 오류 없음)
- 전체 Phase (0~6) 완료
