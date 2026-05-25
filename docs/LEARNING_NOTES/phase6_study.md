# Phase 6 학습 노트 — Next.js UI + CORS + 배포

> 이 파일은 직접 읽으면서 공부하는 용도로 작성되었습니다.
> Next.js App Router, CORS, JWT 클라이언트 사이드 처리의 핵심 개념을 다룹니다.

---

## 1. Next.js App Router — Server vs Client Component

### 기본: Server Component

Next.js 13+ (App Router)에서 `app/` 안의 모든 컴포넌트는 기본적으로 **Server Component**다.

```tsx
// app/some-page/page.tsx — 기본은 Server Component
export default async function SomePage() {
  const data = await fetch("http://api.example.com/data"); // 서버에서 실행
  return <div>{data}</div>;
}
```

서버에서 실행하므로:
- `localStorage`, `window`, `document`에 접근 불가
- `useState`, `useEffect`, `useRef` 같은 훅 사용 불가
- 초기 HTML이 서버에서 렌더링되어 빠른 페이지 로드

### Client Component: "use client"

```tsx
"use client";  // 이 한 줄로 Client Component가 됨

import { useState, useEffect } from "react";

export default function Dashboard() {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch("/api/data")
      .then(r => r.json())
      .then(setData);
  }, []);

  return <div>{data.length}개</div>;
}
```

Client Component는:
- 브라우저에서 실행
- `localStorage`, 이벤트 핸들러, 훅 모두 사용 가능
- 초기 HTML은 서버에서 정적으로 생성, 이후 hydration

### 이 프로젝트에서 Client Component를 쓴 이유

- JWT 인증 체크: `localStorage.getItem("token")`은 브라우저에서만 가능
- 상태 관리: `useState`로 검토 목록, 선택된 영수증, 로딩 상태 관리
- 사이드 이펙트: `useEffect`로 마운트 시 API 호출

---

## 2. JWT 클라이언트 사이드 처리

### localStorage vs Cookie

| | localStorage | Cookie |
|--|--|--|
| JS 접근 | `localStorage.getItem()` | `document.cookie` |
| HttpOnly | 불가 | 가능 (XSS 방어) |
| 자동 전송 | 불가 (수동 헤더 설정) | 자동 (CSRF 취약) |
| 서버 렌더링 | 불가 | 가능 |

이 프로젝트는 localStorage를 사용한다. 간단하고 Next.js 서버 컴포넌트와 충돌이 없다.

### JWT를 Authorization 헤더로 전송

```typescript
// frontend/lib/api.ts
function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};  // SSR에서 오류 방지
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function getPendingReviews() {
  const res = await fetch(`${BASE}/api/v1/reviews/pending`, {
    headers: authHeaders(),  // Authorization: Bearer eyJhbGci...
  });
  ...
}
```

`typeof window === "undefined"` 체크: Server Component나 SSR 환경에서 `localStorage`를 접근하면 오류가 발생한다.

### 401 응답 자동 처리

```typescript
function handleUnauthorized(status: number): void {
  if (status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";  // 로그인 페이지로 강제 이동
  }
}
```

---

## 3. CORS — Cross-Origin Resource Sharing

### 문제: 브라우저의 Same-Origin Policy

브라우저는 보안을 위해 다른 origin으로의 요청을 차단한다.

```
http://localhost:3000 (Next.js)  →  http://localhost:8000 (FastAPI)
                                      다른 포트 = 다른 origin → 차단!
```

### 해결: CORS 헤더

서버가 특정 origin의 요청을 허용한다고 브라우저에게 알린다.

```python
# src/tax_copilot/api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 허용할 origin 목록
    allow_credentials=True,   # Authorization 헤더 포함 요청 허용
    allow_methods=["*"],      # GET, POST, PUT, DELETE 등 모두
    allow_headers=["*"],      # Authorization, Content-Type 등 모두
)
```

브라우저는 실제 요청 전에 `OPTIONS` 메서드로 preflight 요청을 보내서 서버가 허용하는지 확인한다.

### allow_credentials=True와 allow_origins의 관계

```python
# 잘못된 설정 (오류 발생)
CORSMiddleware(allow_origins=["*"], allow_credentials=True)

# 올바른 설정 (구체적인 origin 명시 필요)
CORSMiddleware(allow_origins=["http://localhost:3000"], allow_credentials=True)
```

`credentials=True`는 Authorization 헤더(JWT)를 포함한 요청을 허용한다. 이때 와일드카드(`*`)를 origin으로 쓸 수 없다 — 구체적인 도메인을 지정해야 한다.

---

## 4. 파일 업로드 — FormData

### HTTP에서 파일을 전송하는 방법

파일은 바이너리 데이터다. JSON으로 전송할 수 없다. `multipart/form-data` 인코딩을 사용한다.

```typescript
// frontend/lib/api.ts
async function uploadReceipt(file: File): Promise<...> {
  const form = new FormData();
  form.append("file", file);  // 파일을 form에 추가

  const res = await fetch(`${BASE}/api/v1/receipts?client_company_id=1`, {
    method: "POST",
    headers: authHeaders(),  // Content-Type은 자동으로 multipart/form-data가 됨
    body: form,              // FormData를 body로 전송
  });
  ...
}
```

**주의**: `FormData`를 body로 쓸 때는 `Content-Type` 헤더를 직접 설정하지 않는다. 브라우저가 자동으로 `multipart/form-data; boundary=...`로 설정한다. 직접 설정하면 boundary가 누락되어 파싱 실패.

### React에서 hidden input 패턴

```tsx
const fileRef = useRef<HTMLInputElement>(null);

// 커스텀 버튼 클릭 → hidden input 트리거
<button onClick={() => fileRef.current?.click()}>업로드</button>
<input
  ref={fileRef}
  type="file"
  style={{ display: "none" }}
  onChange={(e) => handleUpload(e.target.files?.[0])}
/>
```

기본 `<input type="file">` UI를 숨기고, 커스텀 버튼으로 제어한다. `ref`를 통해 프로그래밍 방식으로 클릭 이벤트를 발생시킨다.

---

## 5. Render 배포 구조

### render.yaml — 멀티 서비스 정의

```yaml
services:
  - type: web      # HTTP 트래픽을 받는 웹 서버
    name: tax-copilot-api
    env: docker
    healthCheckPath: /healthz

  - type: worker   # HTTP 없이 백그라운드에서 실행
    name: tax-copilot-celery
    env: docker
    dockerCommand: celery -A tax_copilot.workers.celery_app worker
```

`type: web` vs `type: worker`:
- `web`: 외부에서 HTTP 요청을 받을 수 있는 서비스 (FastAPI)
- `worker`: 외부 요청 없이 백그라운드에서 실행 (Celery)

같은 Docker 이미지를 쓰되 실행 명령(`dockerCommand`)으로 역할을 구분한다.

### healthCheckPath가 중요한 이유

Render가 주기적으로 이 경로를 GET해서 서비스가 살아있는지 확인한다. `/healthz`가 응답하지 않으면 서비스를 재시작한다.

```python
@app.get("/healthz", include_in_schema=False)
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})
```

---

## 6. 전체 워크플로우 요약 (End-to-End)

```
1. 세무사가 브라우저에서 /login 접속
   → 이메일/비밀번호 입력
   → POST /api/v1/auth/login → JWT 반환
   → localStorage에 저장, / 로 이동

2. 메인 페이지 로드
   → GET /api/v1/reviews/pending → 검토 대기 영수증 목록

3. 영수증 업로드
   → 파일 선택 → POST /api/v1/receipts (FormData)
   → DB에 PENDING 상태로 저장
   → dispatch_receipt_task() → Redis Queue

4. Celery Worker가 큐에서 태스크를 꺼냄
   → Redis 락 확인 (중복 방지)
   → DB 상태를 PROCESSING으로 변경
   → LangGraph 워크플로우 실행:
     ① image_quality_node (Pillow)
     ② intake_node (Gemini Vision)
     ③ retrieval_node (Qdrant RAG)
     ④ calculation_node (Decimal VAT)
     ⑤ audit_prepare_node (rule-based)
     ⑥ human_review_node (interrupt)
   → DB 상태를 NEEDS_REVIEW로 변경

5. 세무사가 검토 패널에서 영수증 선택
   → 파일명, 업로드 시각, 워크플로우 ID 표시
   → 검토 의견 입력 (선택)
   → [승인] 또는 [반려] 클릭

6. POST /api/v1/reviews/{id}/decide
   → LangGraph Command(resume={"approved": True}) 전송
   → 워크플로우 resume → save_result_node
   → DB 상태를 APPROVED/REJECTED로 변경

7. 검토 완료 → 목록에서 해당 영수증 사라짐
```

---

## 핵심 질문 목록 (면접 준비)

1. "Next.js Server Component와 Client Component의 차이는?"
2. "'use client'를 추가해야 하는 상황을 설명해주세요."
3. "CORS 오류가 발생하는 이유와 해결 방법은?"
4. "allow_credentials=True일 때 allow_origins='*'를 쓸 수 없는 이유는?"
5. "파일 업로드 시 Content-Type을 직접 설정하지 않는 이유는?"
6. "JWT를 localStorage에 저장하는 것의 보안 위험은? 대안은?"
7. "Render에서 web 타입과 worker 타입 서비스의 차이는?"
8. "healthCheck가 왜 중요한가요?"
9. "세무사가 승인 버튼을 눌렀을 때 내부적으로 무슨 일이 일어나나요?"
10. "LangGraph의 interrupt와 resume이 어떻게 동작하나요?"
