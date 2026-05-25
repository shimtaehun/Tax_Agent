# Phase 3 완료 보고서 — RAG 파이프라인

완료일: 2026-05-24

## 목표

거래일 기준 법령 검색 RAG 파이프라인을 구현한다. Phase 2의 mock retrieval_node를 실제 Qdrant + Gemini embedding으로 교체하여, 영수증 거래일에 유효했던 법령만 검색되도록 한다.

---

## 구현한 컴포넌트

### LawChunk 스키마 (`src/tax_copilot/core/rag/schemas.py`)
- Pydantic `BaseModel` 기반, 외부 라이브러리 import 없음 (core 레이어 원칙)
- `effective_from`, `effective_to`, `is_current` 시점 정보 포함
- `is_valid_as_of(date)` 메서드로 거래일 기준 유효성 검사

### Gemini 임베딩 어댑터 (`src/tax_copilot/infra/gemini/embedding.py`)
- `gemini-embedding-2` 모델, dim=768
- 쿼리에 `"query: "` prefix, 문서에 `"passage: "` prefix (검색 정확도 향상)
- `embed_query(text)`, `embed_documents(texts)` 함수

### Qdrant 어댑터 (`src/tax_copilot/infra/vector/qdrant.py`)
- 싱글턴 클라이언트 (`get_client()` / `reset_client()`)
- in-memory 모드 지원 (테스트용) — `get_client(in_memory=True)`
- `ensure_collection()`: collection 없으면 자동 생성
- `upsert_chunks()`: LawChunk 목록 + 벡터를 Qdrant에 저장
- `search_by_date()`: 거래일 기준 필터 검색

### RAG 검색 함수 (`src/tax_copilot/rag/search.py`)
- `search_tax_law(query, as_of_date, top_k=5)` — 공개 API
- Gemini 임베딩 + Qdrant 검색을 조합
- Gemini 실패 시 `ExternalServiceError` 발생

### retrieval_node 교체 (`src/tax_copilot/agents/nodes/retrieval.py`)
- Phase 2 빈 목록 반환 → Phase 3 실제 Qdrant 검색
- `ExternalServiceError` / 기타 예외 → `relevant_laws=[]` (Graceful Degradation)
- API 키 없어도 시스템이 멈추지 않고 HITL 경로로 자동 전환

### 샘플 법령 시드 스크립트 (`scripts/seed_law_corpus.py`)
- 부가가치세법, 법인세법 주요 조항 5개
- `--in-memory` 또는 `--qdrant-url` 옵션
- 실행: `python scripts/seed_law_corpus.py` (GEMINI_API_KEY 필요)

---

## 거래일 기준 필터 설계

### 핵심 조건
```
effective_from <= 거래일
AND (effective_to > 거래일 OR is_current = True)
```

### 구현 방식
날짜를 YYYYMMDD 정수로 저장. Qdrant `Range` 필터가 숫자만 지원하기 때문.

```python
"effective_from_int": int(chunk.effective_from.strftime("%Y%m%d")),
"effective_to_int": 99991231 if is_current else int(effective_to.strftime("%Y%m%d")),
```

현행법(is_current=True)은 `effective_to_int=99991231`로 저장하여, 모든 과거 거래일에 Range 필터를 통과합니다.

---

## 발견한 API 변경점 (중요)

**qdrant-client 1.12+ 에서 `search()` 삭제됨**

| 이전 | 이후 (1.12+) |
|------|-------------|
| `client.search(query_vector=..., ...)` | `client.query_points(query=..., ...)` |
| `results` = list | `response.points` 로 접근 |

qdrant-client를 업그레이드하면 이 변경 사항을 반드시 적용해야 합니다.

---

## 테스트 결과

`tests/test_rag.py` — 11개 전체 통과 (in-memory Qdrant 사용):

| 클래스 | 테스트 수 | 내용 |
|--------|---------|------|
| `TestLawChunkSchema` | 4 | is_valid_as_of() 경계 조건 |
| `TestQdrantUpsertAndSearch` | 5 | upsert/검색, 미래 법령 제외, 구 법령 제외, top_k 제한 |
| `TestRetrievalNodeFallback` | 2 | API 없을 때 fallback, mock 임베딩으로 실제 검색 |

전체 테스트 스위트 49개 통과.

---

## Phase 4 예고

- `intake_node` 교체: Gemini Vision으로 실제 영수증 파싱
  - `transaction_date` 실제 추출 → 거래일 기준 검색이 의미 있어짐
  - `extraction_confidence` 실측값 → HITL 조건 정확해짐
- `image_quality_node` 교체: Gemini Vision으로 실제 이미지 품질 판정
- Gemini Vision 구조화 출력 스키마 설계
