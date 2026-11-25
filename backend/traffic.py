"""OpenCV video input, optional ONNX vehicle detection, and signal estimates."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .config import settings


# COCO class IDs used by common YOLOv8 models.
VEHICLE_CLASSES = {2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck"}


def allocate_green_time(counts: list[int], minimum: int = 10, maximum: int = 40) -> list[int]:
    """Allocate a 60-second demonstration cycle across two approaches."""
    if not counts:
        return []
    if sum(counts) <= 0:
        return [30 for _ in counts]

    available = len(counts) * 30
    total = sum(counts)
    raw = [available * count / total for count in counts]
    bounded = [max(minimum, min(maximum, value)) for value in raw]
    rounded = [int(round(value)) for value in bounded]

    # Keep the displayed total at the nominal cycle time when possible.
    difference = available - sum(rounded)
    order = sorted(range(len(counts)), key=lambda i: counts[i], reverse=True)
    while difference:
        changed = False
        for index in order:
            if difference > 0 and rounded[index] < maximum:
                rounded[index] += 1
                difference -= 1
                changed = True
            elif difference < 0 and rounded[index] > minimum:
                rounded[index] -= 1
                difference += 1
                changed = True
            if difference == 0:
                break
        if not changed:
            break
    return rounded


class VehicleDetector:
    """Load a local YOLOv8 PyTorch model or an OpenCV-compatible ONNX export."""

    def __init__(self) -> None:
        self.net = None
        self.yolo = None
        self.error = ""
        if os.path.isfile(settings.model_path):
            try:
                if Path(settings.model_path).suffix.lower() == ".pt":
                    from ultralytics import YOLO
                    self.yolo = YOLO(settings.model_path)
                elif Path(settings.model_path).suffix.lower() == ".onnx":
                    self.net = cv2.dnn.readNetFromONNX(settings.model_path)
                else:
                    self.error = "Model must be a YOLOv8 .pt or compatible .onnx file."
            except Exception as exc:
                self.error = f"Could not load model: {exc}"
        else:
            self.error = "Model not found; video preview works without detections."

    @property
    def ready(self) -> bool:
        return self.net is not None or self.yolo is not None

    def detect(self, frame: np.ndarray) -> list[dict[str, Any]]:
        if self.yolo is not None:
            results = self.yolo.predict(
                source=frame,
                imgsz=settings.frame_width,
                conf=settings.confidence_threshold,
                verbose=False,
                device="cpu",
            )
            detections = []
            if not results:
                return detections
            for box in results[0].boxes:
                class_id = int(box.cls.item())
                if class_id not in VEHICLE_CLASSES:
                    continue
                x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
                detections.append({
                    "box": [x1, y1, x2 - x1, y2 - y1],
                    "label": VEHICLE_CLASSES[class_id],
                    "confidence": float(box.conf.item()),
                })
            return detections

        if self.net is None:
            return []

        height, width = frame.shape[:2]
        size = settings.frame_width
        scale = min(size / width, size / height)
        scaled_w, scaled_h = int(round(width * scale)), int(round(height * scale))
        resized = cv2.resize(frame, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
        pad_x, pad_y = (size - scaled_w) // 2, (size - scaled_h) // 2
        canvas = np.full((size, size, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + scaled_h, pad_x:pad_x + scaled_w] = resized
        blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, (size, size), swapRB=True, crop=False)

        self.net.setInput(blob)
        output = np.asarray(self.net.forward()).squeeze()
        if output.ndim != 2:
            return []
        # YOLOv8 commonly exports as [channels, candidates]. Also accept the transpose.
        rows = output.T if output.shape[0] < output.shape[1] else output
        boxes: list[list[int]] = []
        scores: list[float] = []
        labels: list[str] = []
        for row in rows:
            if row.size < 6:
                continue
            class_scores = row[4:]
            class_id = int(np.argmax(class_scores))
            confidence = float(class_scores[class_id])
            if class_id not in VEHICLE_CLASSES or confidence < settings.confidence_threshold:
                continue

            center_x, center_y, box_w, box_h = map(float, row[:4])
            left = int((center_x - box_w / 2 - pad_x) / scale)
            top = int((center_y - box_h / 2 - pad_y) / scale)
            right = int((center_x + box_w / 2 - pad_x) / scale)
            bottom = int((center_y + box_h / 2 - pad_y) / scale)
            left, right = max(0, left), min(width, right)
            top, bottom = max(0, top), min(height, bottom)
            if right <= left or bottom <= top:
                continue
            boxes.append([left, top, right - left, bottom - top])
            scores.append(confidence)
            labels.append(VEHICLE_CLASSES[class_id])

        kept = cv2.dnn.NMSBoxes(boxes, scores, settings.confidence_threshold, settings.nms_threshold)
        detections = []
        for item in kept:
            index = int(item[0] if isinstance(item, (tuple, list, np.ndarray)) else item)
            x, y, w, h = boxes[index]
            detections.append({"box": [x, y, w, h], "label": labels[index], "confidence": scores[index]})
        return detections


class TrafficMonitor:
    def __init__(self) -> None:
        self.detector = VehicleDetector()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.capture: cv2.VideoCapture | None = None
        self.jpeg: bytes | None = None
        self.video_source: str | int = settings.video_source
        self.state: dict[str, Any] = {
            "status": "starting",
            "model_ready": self.detector.ready,
            "model_message": self.detector.error,
            "lanes": [{"name": "Approach A", "vehicles": 0, "green_seconds": 30},
                      {"name": "Approach B", "vehicles": 0, "green_seconds": 30}],
            "updated_at": None,
            "message": "Starting video source",
        }

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="traffic-monitor", daemon=True)
        self.thread.start()

    def switch_source(self, source: str | os.PathLike[str]) -> None:
        """Replace the active video source and restart the monitor thread."""
        self.stop_event.set()
        if self.capture:
            self.capture.release()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

        self.stop_event = threading.Event()
        self.video_source = str(source)
        with self.lock:
            self.jpeg = None
            self.state.update(status="starting", message="Opening uploaded video")
        self.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)
        if self.capture:
            self.capture.release()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {**self.state, "lanes": [lane.copy() for lane in self.state["lanes"]]}

    def latest_jpeg(self) -> bytes | None:
        with self.lock:
            return self.jpeg

    def _open_capture(self) -> cv2.VideoCapture:
        source: int | str = settings.camera_index if self.video_source == "camera" else self.video_source
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        return cv2.VideoCapture(source)

    def _run(self) -> None:
        self.capture = self._open_capture()
        if not self.capture.isOpened():
            with self.lock:
                self.state.update(status="waiting", message=f"Cannot open source: {self.video_source}")
            return

        with self.lock:
            self.state.update(status="running", message="Monitoring locally")
        while not self.stop_event.is_set():
            ok, frame = self.capture.read()
            if not ok:
                if isinstance(self.video_source, str) and self.video_source.lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".webm")):
                    self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.05)
                    continue
                with self.lock:
                    self.state.update(status="waiting", message="No frame received from camera source")
                time.sleep(0.5)
                continue

            detections = self.detector.detect(frame)
            height, width = frame.shape[:2]
            split_x = width // 2
            counts = [0, 0]
            cv2.line(frame, (split_x, 0), (split_x, height), (255, 196, 92), 2)
            for detection in detections:
                x, y, w, h = detection["box"]
                lane_index = 0 if x + w / 2 < split_x else 1
                counts[lane_index] += 1
                color = (56, 210, 165) if lane_index == 0 else (255, 196, 92)
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                cv2.putText(frame, f"{detection['label']} {detection['confidence']:.2f}",
                            (x, max(20, y - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            green = allocate_green_time(counts)
            with self.lock:
                self.state.update(
                    status="running", message="Monitoring locally", updated_at=time.time(),
                    lanes=[{"name": "Approach A", "vehicles": counts[0], "green_seconds": green[0]},
                           {"name": "Approach B", "vehicles": counts[1], "green_seconds": green[1]}],
                )
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
                self.jpeg = encoded.tobytes() if ok else None


monitor = TrafficMonitor()
