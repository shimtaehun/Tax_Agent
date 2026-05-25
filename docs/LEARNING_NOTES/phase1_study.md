# Phase 1 학습 노트 — 인증, DB 모델, 파일 업로드

> 코드를 열어서 직접 확인하면서 읽으세요.
> `src/tax_copilot/` 아래 파일들을 참고합니다.

---

## 1. DB 모델 구조 — 왜 이런 설계인가?

### 테이블 5개의 관계

```
tenants (세무사 사무소)
    └── client_companies (고객사) [tenant_id FK]
    └── users (사무소 직원/관리자) [tenant_id FK]
            └── receipts (영수증) [tenant_id FK, client_company_id FK, uploaded_by FK]
                    └── audit_events (이력) [receipt_id FK, tenant_id FK]
```

### tenant가 최상위인 이유 (멀티 테넌시)

세무사 사무소 A와 B가 같은 서비스를 씁니다. A의 데이터가 B에게 보이면 안 됩니다. 이를 위해:

1. 모든 테이블에 `tenant_id`가 있습니다.
2. 모든 쿼리에 `WHERE tenant_id = ?` 조건이 붙습니다.

```python
# src/tax_copilot/api/v1/receipts.py 에서 실제 구현
result = await db.execute(
    select(Receipt).where(
        Receipt.id == receipt_id,
        Receipt.tenant_id == current_user.tenant_id,  # ← 이게 없으면 다른 tenant 데이터 노출
    )
)
```

이걸 빼먹으면 테넌트 간 데이터 누출(IDOR 취약점)이 발생합니다.

### client_company가 필요한 이유

처음에는 "tenant 아래 바로 receipts"를 생각했는데, 설계 리뷰에서 문제를 발견했습니다. 세무사 사무소는 여러 고객사를 담당합니다. 고객사별로 영수증을 분류하고, 고객사별 보고서를 만들어야 합니다. 그래서 `client_companies` 테이블을 추가했고, `receipts.client_company_id`는 NOT NULL입니다.

NOT NULL인 이유: 고객사 없는 영수증은 "누구의 영수증인지 모르는" 상태입니다. 이런 데이터가 있으면 나중에 고객사별 정산이 불가능합니다.

---

## 2. SQLAlchemy Mapped 타입 — 모던 ORM 방식

### 예전 방식

```python
class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True)
    status = Column(String(30), default="PENDING")
```

### 현재 방식 (2.0+ Mapped 타입)

```python
# src/tax_copilot/infra/db/models/receipt.py
class Receipt(Base):
    __tablename__ = "receipts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(30), default=STATUS_PENDING)
    transaction_date: Mapped[date | None] = mapped_column(nullable=True)
```

`Mapped[int]`는 타입 힌트입니다. mypy가 이 컬럼의 타입을 알 수 있습니다. `Mapped[date | None]`은 `nullable=True`와 함께 써서 "None일 수 있는 date"를 표현합니다.

### UniqueConstraint — 중복 방지

```python
# receipt.py:53-55
__table_args__ = (
    UniqueConstraint("tenant_id", "file_hash", name="uq_receipts_tenant_file_hash"),
)
```

같은 tenant 안에서 동일한 파일(같은 SHA-256 해시)을 두 번 올리면 DB에서 오류가 납니다. 이걸 이용해서 중복 업로드를 자동으로 차단합니다.

---

## 3. JWT 인증 — 어떻게 동작하는가?

### JWT(JSON Web Token) 구조

JWT는 세 부분으로 나뉩니다:
```
헤더.페이로드.서명
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI3IiwidGVuYW50X2lkIjoxfQ.XYZ
```

- **헤더**: 알고리즘 (HS256)
- **페이로드**: 실제 데이터 (user_id, tenant_id, role, 만료시각)
- **서명**: 서버만 아는 secret_key로 서명 → 위조 불가능

### 이 프로젝트 구현

```python
# src/tax_copilot/auth/jwt.py
def create_access_token(user_id: int, tenant_id: int, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=60 * 8)  # 8시간
    payload = {
        "sub": str(user_id),     # subject (표준 클레임)
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")
```

`sub` 클레임은 JWT 표준에서 "이 토큰의 주체(대상 사용자)"를 나타내는 필드입니다.

### 인증 흐름

```
클라이언트                                    서버
   │── POST /auth/login (username, password) ──→ │
   │                                             │ DB에서 user 조회
   │                                             │ bcrypt로 비밀번호 검증
   │←── { access_token: "eyJ..." } ─────────────│
   │
   │── GET /receipts (Authorization: Bearer eyJ...) ──→ │
                                                         │ JWT 서명 검증
                                                         │ payload에서 tenant_id, role 추출
                                                         │ CurrentUser 생성
```

---

## 4. bcrypt — 비밀번호 안전하게 저장하기

### 왜 비밀번호를 그냥 저장하면 안 되는가?

DB가 해킹당하면 모든 비밀번호가 노출됩니다. 그래서 비밀번호를 "해시"로 저장합니다. 해시는 원래 값을 되돌릴 수 없습니다.

### MD5, SHA-256은 왜 안 되는가?

빠르기 때문입니다. 해커가 10억 개의 해시를 1초에 계산해서 비밀번호를 역추적(무차별 대입)할 수 있습니다.

### bcrypt가 좋은 이유

의도적으로 느립니다. "cost factor"로 계산 비용을 조절합니다. 컴퓨터가 빨라져도 cost factor를 높이면 됩니다. 또 같은 비밀번호도 매번 다른 해시가 나옵니다(salt 때문에).

```python
# src/tax_copilot/auth/password.py
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

`gensalt()`가 랜덤 salt를 생성합니다. 그래서 같은 비밀번호여도 해시가 매번 다릅니다.

### passlib을 안 쓴 이유

`passlib`은 Python 3.12 + bcrypt 4.x 조합에서 버그가 있습니다. `detect_wrap_bug`라는 내부 함수가 72바이트 넘는 테스트 문자열을 bcrypt에 전달하는데, bcrypt 4.x는 이를 거부합니다. `bcrypt`를 직접 쓰면 이 문제가 없습니다.

---

## 5. magic bytes — 파일 형식 검증

### Content-Type 헤더를 왜 믿으면 안 되는가?

HTTP 요청을 보낼 때 `Content-Type: image/jpeg`는 클라이언트가 직접 설정합니다. 악성 파일을 올리면서 `Content-Type`만 바꾸면 서버가 속습니다.

### magic bytes란?

파일 형식마다 첫 몇 바이트가 고정되어 있습니다:
- JPEG: `\xFF\xD8\xFF`
- PNG: `\x89PNG\r\n\x1a\n`
- PDF: `%PDF`

파일 내용의 실제 첫 바이트를 읽으면 진짜 형식을 알 수 있습니다.

```python
# src/tax_copilot/core/receipts/validation.py:17-22
_MAGIC: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"%PDF": "application/pdf",
}

def detect_mime_type(data: bytes) -> str | None:
    for magic, mime in _MAGIC.items():
        if data[: len(magic)] == magic:
            return mime
    return None
```

### 이중 검증 (확장자 + magic bytes)

magic bytes만 검사하면: `.pdf` 확장자 파일에 JPEG 내용을 넣을 수 있습니다.
확장자만 검사하면: `.jpg` 확장자 파일에 악성 스크립트를 넣을 수 있습니다.

둘 다 검사해서 일치해야만 통과합니다:

```python
# validation.py:46-57
ext = filename.rsplit(".", 1)[-1].lower()
expected_mime = _EXT_TO_MIME.get(ext)  # 확장자 기준 기대 MIME
mime = detect_mime_type(content)       # 실제 내용 기준 MIME

if mime != expected_mime:
    raise ValidationError("파일 확장자와 내용 형식이 일치하지 않습니다.")
```

---

## 6. SHA-256 파일 해시 — 중복 업로드 방지

### 아이디어

파일 내용이 완전히 같으면 SHA-256 해시도 완전히 같습니다. 이를 이용합니다.

```
파일 A (영수증.jpg) → SHA-256 → "a1b2c3d4..."
파일 B (영수증_복사본.jpg) → SHA-256 → "a1b2c3d4..."  ← 같은 해시!
```

DB에서 `(tenant_id, file_hash)` UniqueConstraint를 걸어두면, 같은 파일을 두 번 올리면 DB가 거부합니다.

```python
# src/tax_copilot/core/receipts/validation.py:62-64
def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
```

### 왜 파일명이 아닌 내용 해시인가?

파일명은 바꿀 수 있습니다. `영수증.jpg`를 `영수증_2차.jpg`로 바꿔서 올리면 파일명 기준으로는 다른 파일처럼 보입니다. 내용이 같으면 내용 해시도 같습니다.

---

## 7. 로컬 파일 저장 경로 구조

```python
# src/tax_copilot/infra/storage/local.py
# 경로: receipts/{tenant_id}/{hash[:2]}/{hash}.{ext}
# 예: receipts/1/a1/a1b2c3d4...abcd.jpg
```

### 왜 `hash[:2]` 서브폴더를 만드는가?

한 폴더에 파일이 너무 많으면 파일 시스템이 느려집니다 (특히 ext4, HFS+). 해시의 앞 두 글자로 서브폴더를 만들면 파일이 256개 폴더에 균등하게 분산됩니다 (16진수 2자리 = 256가지 조합). git의 objects/ 폴더도 같은 방식을 씁니다.

---

## 8. 감사 로그 (Audit Events)

### 왜 필요한가?

세무 관련 서비스에서는 "언제, 누가, 어떤 상태로 바꿨는가"를 추적해야 합니다. 세무 감사나 분쟁 발생 시 이력이 증거가 됩니다.

```python
# src/tax_copilot/audit/events.py
async def record_event(
    db: AsyncSession,
    *,
    tenant_id: int,
    event_type: str,       # RECEIPT_UPLOADED, AI_EXTRACTION_COMPLETED 등
    payload: dict,         # 이벤트 상세 정보
    actor_user_id: int | None = None,
    receipt_id: int | None = None,
) -> None:
    ...
```

영수증 업로드 → RECEIPT_UPLOADED 이벤트
AI 처리 완료 → AI_EXTRACTION_COMPLETED 이벤트
세무사 승인 → HUMAN_REVIEW_COMPLETED 이벤트

---

## 핵심 질문 목록 (면접 준비)

1. "멀티 테넌시에서 데이터 격리를 어떻게 구현했나요?"
2. "비밀번호를 어떻게 저장하고 검증했나요? SHA-256은 왜 안 되나요?"
3. "JWT의 세 부분은 무엇이고, 위조는 어떻게 방지하나요?"
4. "파일 업로드에서 어떤 보안 검증을 했나요?"
5. "같은 파일을 두 번 올리는 것을 어떻게 방지했나요?"
6. "감사 로그가 왜 필요한가요?"
7. "magic bytes 검사와 확장자 검사를 둘 다 해야 하는 이유는?"
