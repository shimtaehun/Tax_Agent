from dataclasses import dataclass
from struct import unpack


@dataclass(frozen=True)
class ImageDimensions:
    width: int
    height: int


@dataclass(frozen=True)
class ImageQualityResult:
    status: str
    reason: str | None
    dimensions: ImageDimensions | None
    file_size_bytes: int

    @property
    def is_readable(self) -> bool:
        return self.status == "readable"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "dimensions": (
                None
                if self.dimensions is None
                else {"width": self.dimensions.width, "height": self.dimensions.height}
            ),
            "file_size_bytes": self.file_size_bytes,
        }


def _png_dimensions(content: bytes) -> ImageDimensions | None:
    if len(content) < 24 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    width, height = unpack(">II", content[16:24])
    return ImageDimensions(width=width, height=height)


def _jpeg_dimensions(content: bytes) -> ImageDimensions | None:
    if len(content) < 4 or not content.startswith(b"\xff\xd8"):
        return None

    index = 2
    while index + 9 < len(content):
        if content[index] != 0xFF:
            index += 1
            continue
        marker = content[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(content):
            return None
        segment_length = int.from_bytes(content[index : index + 2], "big")
        if segment_length < 2 or index + segment_length > len(content):
            return None
        if 0xC0 <= marker <= 0xC3:
            height = int.from_bytes(content[index + 3 : index + 5], "big")
            width = int.from_bytes(content[index + 5 : index + 7], "big")
            return ImageDimensions(width=width, height=height)
        index += segment_length
    return None


def detect_dimensions(content: bytes, mime_type: str) -> ImageDimensions | None:
    if mime_type == "image/png":
        return _png_dimensions(content)
    if mime_type == "image/jpeg":
        return _jpeg_dimensions(content)
    return None


def check_image_quality(
    content: bytes,
    mime_type: str,
    *,
    min_width: int = 600,
    min_height: int = 300,
    min_size_bytes: int = 128,
) -> ImageQualityResult:
    if mime_type not in {"image/png", "image/jpeg"}:
        return ImageQualityResult(
            "unsupported",
            "Vision MVP only accepts PNG/JPEG",
            None,
            len(content),
        )
    if len(content) < min_size_bytes:
        return ImageQualityResult("unreadable", "file_too_small", None, len(content))

    dimensions = detect_dimensions(content, mime_type)
    if dimensions is None:
        return ImageQualityResult("unreadable", "cannot_decode_dimensions", None, len(content))
    if dimensions.width < min_width or dimensions.height < min_height:
        return ImageQualityResult("unreadable", "image_too_small", dimensions, len(content))

    return ImageQualityResult("readable", None, dimensions, len(content))
