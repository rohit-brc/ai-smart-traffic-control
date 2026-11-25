"""Environment-backed settings for the local traffic demo."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("YOLO_CONFIG_DIR", str(Path(__file__).resolve().parents[1] / ".ultralytics"))


@dataclass(frozen=True)
class Settings:
    video_source: str = os.getenv("VIDEO_SOURCE", "media/traffic.mp4")
    model_path: str = os.getenv("MODEL_PATH", "models/vehicle_detector.pt")
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.40"))
    nms_threshold: float = float(os.getenv("NMS_THRESHOLD", "0.45"))
    camera_index: int = int(os.getenv("CAMERA_INDEX", "0"))
    frame_width: int = int(os.getenv("FRAME_WIDTH", "640"))


settings = Settings()
