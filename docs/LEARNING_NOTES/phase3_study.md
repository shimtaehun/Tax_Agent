# Phase 3 학습 노트 — RAG 파이프라인

> 이 파일은 직접 읽으면서 공부하는 용도로 작성되었습니다.
> RAG(Retrieval-Augmented Generation)의 핵심 개념과 이 프로젝트의 구현을 다룹니다.

---

## 1. RAG란 무엇인가?

### LLM의 한계

LLM(대형 언어 모델)은 학습 시점의 지식만 갖고 있습니다. 2024년 1월에 개정된 세법을 모를 수 있습니다. 또 환각(hallucination)으로 없는 법조문을 만들어낼 수 있습니다.

### RAG 해결 방법

```
[사용자 질문]
     ↓
[관련 문서 검색 (Retrieval)]  ← 실제 법령 DB에서
     ↓
[검색 결과 + 질문을 함께 LLM에 전달 (Augmented Generation)]
     ↓
[근거 있는 답변]
```

LLM이 판단할 때 "신뢰할 수 있는 문서"를 먼저 찾아서 함께 제공합니다. LLM이 그 문서를 참고해서 답변하므로 근거가 있고 환각이 줄어듭니다.

### 이 프로젝트에서의 RAG

```
[영수증 거래 정보]
     ↓
[검색 쿼리 생성: "부가세 매입세액 공제 신용카드"]
     ↓
[Qdrant에서 관련 법령 chunk 검색]  ← 거래일 기준 필터!
     ↓
[법령 chunk + 영수증 → audit_prepare_node(LLM)]
     ↓
[부가세 공제 여부 판단]
```

---

## 2. 벡터 검색 (Vector Search) — 어떻게 "관련" 문서를 찾는가?

### 키워드 검색의 한계

`"매입세액 공제"` 로 검색하면 정확히 그 단어가 있는 문서만 나옵니다. "부가세 환급"이라고 표현된 같은 개념의 문서는 안 나옵니다.

### 임베딩 (Embedding)

텍스트를 숫자 배열(벡터)로 변환합니다. 의미가 비슷한 텍스트는 벡터 공간에서 가까운 위치에 있습니다.

```python
"매입세액 공제"  →  [0.12, -0.34, 0.89, ...]  (768차원)
"부가세 환급"    →  [0.11, -0.33, 0.91, ...]  ← 비슷한 벡터!
"접대비 한도"    →  [-0.45, 0.67, -0.12, ...]  ← 다른 벡터
```

임베딩 모델이 이 변환을 담당합니다. 이 프로젝트에서는 `gemini-embedding-2`를 사용합니다.

### 코사인 유사도

두 벡터가 얼마나 가까운지 측정합니다. 1에 가까울수록 유사, -1에 가까울수록 반대 의미입니다.

```python
# Qdrant collection 생성 시
VectorParams(size=768, distance=Distance.COSINE)
```

---

## 3. 이 프로젝트의 핵심: 거래일 기준 검색

### 왜 현재 날짜로 검색하면 안 되는가?

2023년 6월 거래의 부가세 공제 여부를 심사할 때, 현재(2026년) 시행 중인 법령으로 판단하면 안 됩니다. 거래가 발생한 시점의 법령으로 판단해야 합니다.

2024년 개정으로 "신용카드 공제율이 변경"되었다면:
- 2023년 거래 → 2023년 법령 적용
- 2024년 거래 → 2024년 개정 법령 적용

### 법령 시행일 데이터 구조

```
부가가치세법 제38조 (2014년 시행)
  effective_from: 2014-01-01
  effective_to: None (현행법)
  is_current: True

부가가치세법 제38조 구버전 (2014년 이전)
  effective_from: 2010-01-01
  effective_to: 2014-01-01
  is_current: False
```

### 필터 조건

```
effective_from <= 거래일
AND (effective_to > 거래일 OR is_current = True)
```

풀어서 설명:
1. 법령이 거래일 이전에 시행되었어야 함 (`effective_from <= 거래일`)
2. 법령이 아직 유효해야 함:
   - `effective_to > 거래일`: 개정 전이라 아직 유효
   - `is_current = True`: 현행법이라 유효

### 코드 구현

```python
# src/tax_copilot/infra/vector/qdrant.py
as_of_int = float(int(as_of_date.strftime("%Y%m%d")))  # 20240615

must = [FieldCondition(key="effective_from_int", range=Range(lte=as_of_int))]
should = [
    FieldCondition(key="effective_to_int", range=Range(gt=as_of_int)),
    FieldCondition(key="is_current", match=MatchValue(value=True)),
]
```

**왜 날짜를 정수로 저장하는가?** Qdrant의 `Range` 필터는 숫자만 지원합니다. ISO 날짜 문자열(`"2024-06-15"`)은 지원하지 않습니다. `20240615`로 변환하면 크기 비교가 정확합니다 (20230615 < 20240615 < 20250615).

---

## 4. LawChunk 스키마 설계

```python
# src/tax_copilot/core/rag/schemas.py
class LawChunk(BaseModel):
    chunk_id: str    # 예: "vat-art38-p1-7f3a9c1a"
    law_id: str      # 예: "vat" (부가가치세법)
    law_name: str
    article_no: str  # 예: "제38조"
    content: str     # 실제 법령 텍스트

    effective_from: date
    effective_to: date | None    # None = 현행법
    is_current: bool

    corpus_version: str   # 어떤 버전 코퍼스인지 추적
```

### chunk_id 형식

```
{법령약어}-art{조번호}-p{항번호}-{해시8자리}
vat-art38-p1-7f3a9c1a
```

단순히 법령명 + 조문 번호만으로 ID를 만들면 문제가 생깁니다. 같은 조문이 개정되면 두 버전이 생기는데, 같은 ID가 두 개 있게 됩니다. 내용 해시를 포함하면 버전마다 고유 ID가 됩니다.

---

## 5. 레이어 설계 — 어디에 무엇을 두는가?

```
core/rag/schemas.py      ← LawChunk 스키마 (pydantic만, 외부 라이브러리 없음)
infra/gemini/embedding.py ← Gemini API 호출 (infra 레이어)
infra/vector/qdrant.py   ← Qdrant 클라이언트 (infra 레이어)
rag/search.py            ← 두 어댑터를 합쳐서 search_tax_law() 제공
agents/nodes/retrieval.py ← search_tax_law() 호출 + fallback 처리
```

`core/`에 `LawChunk`를 두고 Qdrant import를 금지한 이유: 나중에 Qdrant를 다른 벡터 DB로 교체해도 `core/` 코드를 수정할 필요가 없습니다.

---

## 6. Graceful Degradation — API 없어도 시스템이 멈추지 않는다

Gemini API 키가 없거나, Qdrant가 다운되면 어떻게 할까요?

```python
# src/tax_copilot/agents/nodes/retrieval.py
async def tax_law_retrieval_node(state: AgentState) -> dict:
    try:
        results = await search_tax_law(query, as_of_date)
        return {"relevant_laws": results, ...}
    except ExternalServiceError:
        # 검색 실패 → 빈 목록 반환
        return {"relevant_laws": [], ...}
```

`relevant_laws = []`이면 `audit_prepare_node`에서 `requires_human = True`가 됩니다. 자동 판단 대신 세무사에게 HITL로 넘어갑니다. 시스템이 멈추지 않고 사람이 처리합니다.

이것이 **Graceful Degradation** 패턴입니다. 외부 서비스 장애가 전체 시스템 장애로 이어지지 않습니다.

---

## 7. Qdrant 싱글턴 패턴

```python
# src/tax_copilot/infra/vector/qdrant.py
_client: QdrantClient | None = None

def get_client(*, in_memory: bool = False, url: str | None = None) -> QdrantClient:
    global _client
    if _client is None:
        if in_memory:
            _client = QdrantClient(":memory:")
        else:
            _client = QdrantClient(url=url or settings.qdrant_url)
    return _client
```

처음 호출할 때만 클라이언트를 만들고, 이후에는 같은 객체를 재사용합니다. 매 요청마다 새 연결을 만들면 느립니다.

테스트에서는 `reset_client()`로 싱글턴을 초기화하고, `in_memory=True`로 새 in-memory 클라이언트를 만듭니다.

---

## 8. 임베딩 prefix 전략

```python
# src/tax_copilot/infra/gemini/embedding.py
_QUERY_PREFIX = "query: "    # 검색 쿼리에 붙임
_DOC_PREFIX = "passage: "   # 법령 문서에 붙임
```

왜 prefix를 붙이는가? 임베딩 모델이 "이것이 질문인지, 답변인지" 구분할 수 있게 합니다. 질문과 답변의 임베딩 공간이 잘 정렬되어 검색 정확도가 높아집니다.

검색할 때: `"query: 부가세 매입세액 공제 신용카드"`
저장할 때: `"passage: 매입세액은 다음 각 호의 것으로 한다..."`

---

## 9. 현재 Phase 3 구현의 한계

| 항목 | 현재 상태 | 개선 방향 |
|------|----------|----------|
| 임베딩 | Gemini API 필요 | mock으로 테스트 가능 |
| 법령 데이터 | 수동 샘플 5개 | law.go.kr API로 자동 수집 |
| Qdrant | in-memory | 외부 서버 연결 (Phase 5) |
| 리랭킹 | 없음 | FlashRank (백로그) |
| intake_node | mock (confidence=0.95) | Phase 4에서 Gemini Vision으로 교체 |

intake_node가 mock이기 때문에 모든 영수증이 `transaction_date = today`입니다. Phase 4에서 실제 날짜를 추출하면 거래일 기준 검색이 의미 있어집니다.

---

## 핵심 질문 목록 (면접 준비)

1. "RAG가 순수 LLM 방식보다 나은 점은?"
2. "왜 거래일 기준으로 법령을 검색해야 하나요? 현재 날짜로 하면 안 되는 이유는?"
3. "벡터 검색에서 코사인 유사도란 무엇인가요?"
4. "임베딩 모델을 교체하면 어떤 작업이 필요한가요?" (전체 재임베딩)
5. "Qdrant에서 날짜를 정수로 저장한 이유는?"
6. "Gemini API가 다운됐을 때 시스템이 어떻게 동작하나요?" (Graceful Degradation)
7. "chunk_id에 내용 해시를 포함한 이유는?"
8. "이 프로젝트에서 RAG의 한계는?" (법령 5개 샘플, intake mock)
