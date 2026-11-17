from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    width: int = 512
    height: int = 512


@dataclass(frozen=True)
class ImageResult:
    content: bytes
    media_type: str
    provider: str
    model: str
    requires_review: bool = True


class ImageProvider(Protocol):
    def generate(self, request: ImageRequest) -> ImageResult: ...


class UnconfiguredProvider:
    def generate(self, request: ImageRequest) -> ImageResult:
        raise RuntimeError(
            "Image generation is unavailable until a benchmarked provider is configured."
        )


def get_provider(name: str = "disabled") -> ImageProvider:
    if name != "disabled":
        raise ValueError(
            "Local and hosted adapters require implementation and benchmarking in Step 2."
        )
    return UnconfiguredProvider()
