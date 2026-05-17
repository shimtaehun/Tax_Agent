# Phase 6 Portfolio Notes

## 가장 어려웠던 기술 결정

HITL workflow에서 어디까지를 자동화하고 어디부터 세무사 검토로 넘길지 정하는 것이 핵심이었다. 세무 도메인은 "그럴듯한 자동 판단"보다 재현 가능한 근거와 승인 기록이 중요하므로, AI 판단은 draft로 제한하고 최종 결정은 human review 이후 저장하는 구조를 선택했다.

## 왜 LangGraph인가

일반 함수 체인이나 Celery task 하나로도 순차 처리는 가능하다. 하지만 Tax-Copilot은 중간에 멈추고, 세무사 입력으로 같은 thread를 재개해야 한다. LangGraph의 interrupt/resume은 이 상태 기반 workflow를 명시적으로 표현할 수 있어 적합했다.

## 거래일 기준 법령 검색

세무 판단은 현재 법령 기준이 아니라 거래일 당시 시행 법령 기준이어야 한다. 그래서 `LawChunk`에 `effective_from`, `effective_to`, `content_hash`, `corpus_version`을 저장하고, retrieval에서 `as_of_date`를 필터로 사용했다. 테스트에서는 2024-12-31과 2025-01-01의 meal purchase 검색 결과가 달라지는 것을 확인한다.

## AI 오판 대응

LLM은 계산하지 않는다. VAT 계산은 `Decimal` 기반 deterministic tool이 담당한다. 법적 근거가 부족하거나 이미지 품질이 낮거나 business purpose가 불명확하면 `requires_human_review=True`로 세무사 검토에 넘긴다.

## 비용 통제

품질 분류에 AI를 먼저 호출하지 않고 PNG/JPEG dimension 기반 deterministic check를 먼저 수행한다. RAG도 mini corpus와 Qdrant adapter부터 구현해 외부 API 호출 없이 core workflow를 검증했다.

## 시스템 한계

현재 mini corpus는 실제 세법 전체를 대체하지 못한다. Gemini Vision adapter는 boundary만 있고 live extraction은 API key 설정 이후 구현해야 한다. 실제 배포에서는 PostgreSQL checkpointer setup, law.go.kr collector, object storage lifecycle, auth hardening이 필요하다.

## 가장 많이 배운 점

AI workflow는 모델 호출보다 상태, 재시도, 감사 가능성, 사람이 개입하는 지점을 명확히 설계하는 일이 더 중요하다. 특히 resume 시 재실행되는 노드에 side effect가 있으면 중복 저장이나 중복 과금이 발생할 수 있어 prepare/interrupt/save 분리가 필요했다.
