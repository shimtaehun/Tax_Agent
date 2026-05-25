# ADR 0001 — pip + pip-tools for dependency management

Date: 2026-05-24
Status: Accepted

## Context

Python 패키지 관리 도구로 pip-tools, uv, Poetry 중 선택이 필요했다.
배포 대상은 Railway 또는 Render이며, 1인 개발 포트폴리오 프로젝트다.

## Decision

pip + pip-tools를 사용한다.

- `requirements/base.in`: 직접 선언한 의존성
- `requirements/dev.in`: 개발 도구 (base.in 포함)
- `pip-compile`로 `.txt` lock 파일 생성

## Consequences

**Good:**
- `requirements.txt` 기반 배포 → Railway/Render 빌더 추가 설정 불필요
- `.in` 파일에서 상위 버전 범위 지정, `.txt`에서 hash pinning → 재현성 보장
- Poetry/uv 대비 onboarding 부담 없음

**Bad:**
- uv에 비해 속도가 느림
- lock 파일 충돌 시 수동 해결 필요

필요 시 uv로 마이그레이션 가능한 구조 유지.
