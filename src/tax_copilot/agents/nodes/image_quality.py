"""이미지 품질 확인 노드.

Phase 4: Pillow로 결정론적 품질 검사.
  1. 파일 크기 (1KB 미만 → unreadable)
  2. 이미지 디코드 가능 여부 (손상된 파일 → unreadable)
  3. 최소 해상도 (64×64 미만 → unreadable)

Phase 4에서 Gemini Vision 품질 분류를 추가하지 않는다.
이유: Gemini 호출은 비용이 크고, 결정론적 체크만으로도 명백한 불량 파일을 걸러낼 수 있다.
Gemini Vision은 intake_node에서 한 번만 호출한다 (비용 최적화).
"""

import os

from tax_copilot.agents.state import AgentState

_MIN_BYTES = 1024  # 1KB 미만
_MIN_DIMENSION = 64  # 64px 미만 (가로 또는 세로)


async def image_quality_node(state: AgentState) -> dict:
    """파일 크기와 이미지 디코드 가능 여부로 품질을 판정한다."""
    file_path = state["file_path"]

    # 1단계: 파일 존재와 크기 확인
    try:
        size = os.path.getsize(file_path)
    except OSError:
        return {
            "image_quality": "unreadable",
            "error_message": f"파일을 읽을 수 없습니다: {file_path}",
        }

    if size < _MIN_BYTES:
        return {"image_quality": "unreadable", "error_message": "파일 크기가 너무 작습니다."}

    # 2단계: 이미지 디코드 가능 여부 + 최소 해상도 (PDF는 건너뜀)
    if file_path.lower().endswith(".pdf"):
        return {"image_quality": "ok"}

    quality, error = _check_image_decodable(file_path)
    return {"image_quality": quality, "error_message": error}


def _check_image_decodable(file_path: str) -> tuple[str, str | None]:
    """Pillow로 이미지를 열어 손상 여부와 최소 해상도를 확인한다."""
    try:
        from PIL import Image

        with Image.open(file_path) as img:
            img.verify()  # 파일 헤더와 구조 검증 (실제 디코드 없이)

        # verify() 후 재오픈 필요 (verify 후 파일 포인터가 닫힘)
        with Image.open(file_path) as img:
            width, height = img.size
            if width < _MIN_DIMENSION or height < _MIN_DIMENSION:
                msg = (
                    f"이미지 해상도가 너무 낮습니다: {width}×{height}px"
                    f" (최소 {_MIN_DIMENSION}×{_MIN_DIMENSION}px)"
                )
                return ("unreadable", msg)

        return "ok", None

    except (OSError, Exception) as exc:  # noqa: BLE001
        return "unreadable", f"이미지를 열 수 없습니다: {exc}"
