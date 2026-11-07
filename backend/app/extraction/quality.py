"""Image quality metrics, so the app can ask for a retake early."""
from dataclasses import asdict, dataclass

# Below these, OCR results are usually unreliable.
MIN_SHARPNESS = 60.0
MIN_BRIGHTNESS = 50.0
MAX_BRIGHTNESS = 230.0
MIN_SIDE_PX = 500


@dataclass
class QualityMetrics:
    decodable: bool
    width: int = 0
    height: int = 0
    brightness: float = 0.0  # mean grayscale intensity 0-255
    sharpness: float = 0.0  # Laplacian variance; higher = sharper
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["issues"] = list(self.issues)
        return data


def analyze_image(file_bytes: bytes, mime_type: str) -> QualityMetrics | None:
    """Measure an image. Returns None for non-images (e.g. PDFs)."""
    if not mime_type.startswith("image/"):
        return None
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None
    img = cv2.imdecode(np.frombuffer(file_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return QualityMetrics(decodable=False, issues=("File is not a readable image.",))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    brightness = round(float(gray.mean()), 1)
    sharpness = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1)
    issues = []
    if sharpness < MIN_SHARPNESS:
        issues.append("Photo looks blurry. Hold steady and retake.")
    if brightness < MIN_BRIGHTNESS:
        issues.append("Photo is too dark.")
    elif brightness > MAX_BRIGHTNESS:
        issues.append("Photo is overexposed (glare?).")
    if min(h, w) < MIN_SIDE_PX:
        issues.append(f"Resolution is low ({w}x{h}).")
    return QualityMetrics(True, w, h, brightness, sharpness, tuple(issues))
