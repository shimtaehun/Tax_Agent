# ADR 0001 — pip-tools로 의존성 관리

Date: 2026-05-17
Status: Accepted

## Context

Python 의존성 관리 도구로 pip freeze, Poetry, uv, pip-tools 중 선택해야 한다.
포트폴리오 프로젝트이므로 현업 표준에 가까운 도구를 선택하되 학습 비용이 낮아야 한다.

## Decision

pip + pip-tools 조합을 사용한다.
- `requirements/*.in` — 직접 선언한 의존성 (git 추적)
- `requirements/*.txt` — pip-compile이 생성한 전체 트리 (gitignore)
- 환경 분리: base.in (공통) / dev.in (개발)

## Consequences

- Poetry/uv 대비 lock 파일이 없으나, .txt 파일이 동일 역할 수행
- 패키지 업그레이드 시 `pip-compile --upgrade` 한 번으로 전체 갱신 가능
- 상세는 git history 참조
