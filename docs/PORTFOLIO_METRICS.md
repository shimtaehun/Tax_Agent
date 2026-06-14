# Tax-Copilot — 포트폴리오 핵심 수치

> 모든 수치는 재현 가능한 방법으로 측정했으며, 면접 시 측정 방법까지 설명 가능합니다.

---

## 1. HITL 자동화율 (설계 핵심 지표)

### 설계 의도
AI 판단만으로 처리할 수 있는 영수증은 자동 완료하고,
신뢰도가 낮거나 리스크가 있는 건만 세무사에게 넘기는 구조.

### 임계값 기준 (코드: `src/tax_copilot/agents/nodes/audit_prepare.py`)
| 조건 | 처리 경로 |
|------|-----------|
| `confidence ≥ 0.8` AND `risk_flag 없음` | 자동 처리 (HITL 없음) |
| `confidence < 0.8` OR `risk_flag 존재` | 세무사 검토 (HITL) |

### 측정 방법
```sql
-- 전체 처리 건수 대비 상태별 비율
SELECT
  status,
  COUNT(*)                                        AS 건수,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS 비율
FROM receipts
GROUP BY status;
```

### 현재 상태
운영 샘플 데이터 축적 중. 영수증 50건 이상 처리 후 측정 예정.

---

## 2. 법령 코퍼스 규모

### 수치
| 컬렉션 | 설명 | chunk 수 |
|--------|------|----------|
| `tax_laws` | 법령 본문 (부가가치세법·법인세법·소득세법·조세특례제한법) | **1,626건** |
| `tax_cases` | 국세청 해석례 + 조세심판원 심판례 | **704건** |
| **합계** | | **2,330건** |

### 구성
- 법제처 Open API에서 현행 법령 조문 수집
- 국세청 법령해석 사례 (`ntsCgmExpc`)
- 조세심판원 특별행정심판례 (`ttSpecialDecc`)
- 청킹: 1,200자 단위 + 150자 오버랩

### 검색 전략
법령 본문(`tax_laws`) 우선 검색 → 결과 2건 미만일 때 심판례(`tax_cases`)로 보완.
유사도 임계값 0.65 이하 결과는 노이즈로 판단해 미표시.

### 측정 방법
```python
from qdrant_client import QdrantClient
c = QdrantClient(url="http://localhost:6333")
print(c.get_collection("tax_laws").points_count)   # 1626
print(c.get_collection("tax_cases").points_count)  # 704
```

---

## 3. 테스트 커버리지

### 수치
| 항목 | 값 |
|------|----|
| 전체 테스트 수 | **166개** |
| 라인 커버리지 | **83%** |
| 테스트 통과율 | **100%** (166/166) |

### 측정 방법
```bash
pytest --cov=tax_copilot --cov-report=term-missing
# 166 passed in 9.02s  |  TOTAL 2613 lines, 83% coverage
```

### 커버리지 대상
- 에이전트 노드 (LangGraph 6개 노드)
- API 엔드포인트 (FastAPI v1)
- 도메인 규칙 (세무 판단 룰엔진)
- 인프라 어댑터 (Qdrant, Gemini, Celery)

---

## 측정 재현 방법

```bash
# 1. 자동화율 — DB에 영수증 데이터가 있을 때
python3 -c "
import asyncio, sys; sys.path.insert(0, 'src')
async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from tax_copilot.core.config import settings
    from sqlalchemy import text
    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as s:
        rows = (await s.execute(text(
            'SELECT status, COUNT(*), ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(),1) FROM receipts GROUP BY status'
        ))).fetchall()
        for r in rows: print(r)
asyncio.run(main())
"

# 2. 코퍼스 규모
python3 -c "
import sys; sys.path.insert(0, 'src')
from qdrant_client import QdrantClient
c = QdrantClient(url='http://localhost:6333')
print('법령 본문:', c.get_collection('tax_laws').points_count)
print('심판례/해석례:', c.get_collection('tax_cases').points_count)
"

# 3. 테스트 커버리지
pytest --tb=no -q --cov=tax_copilot --cov-report=term-missing
```
