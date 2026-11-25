# AI Based Smart Traffic Control System

**Created by Rohit Basu Roy Chowdhury**

A locally run demonstration that reads a traffic video or ESP32-CAM stream, detects vehicles with a user-supplied YOLOv8 model, estimates vehicle load in two screen regions, and displays suggested green-time allocations.

The source code in this repository was written independently for this version; it does not carry forward the source repository's files or Git history. The GitHub-ready repository excludes local settings, model weights, and traffic footage. Those files may exist on your PC, but they are ignored by Git.

> **Safety:** This is a demonstration and decision-support prototype. It is not certified for controlling public-road signals or safety-critical infrastructure. Do not connect it to live traffic equipment.

## Requirements

- Python 3.10 or newer
- A YOLOv8 `.pt` model, or a compatible `.onnx` export, with COCO class ordering
- A video file you own or have permission to use, or an ESP32-CAM on your local network

The model and traffic footage are intentionally not included in the repository. Before downloading or sharing a model, check its license and the license of its training data. For local use, put a permitted YOLOv8 model at `models/vehicle_detector.pt`; `backend/traffic.py` also accepts a compatible ONNX model. The optional Ultralytics package and model are available under AGPL-3.0 or Enterprise terms; this project uses AGPL-3.0.

## Run locally

From the project root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
```

Place a video you are allowed to use at `media/traffic.mp4`, or edit `VIDEO_SOURCE` in `.env` to a local path or ESP32-CAM stream URL such as `http://192.168.1.50:81/stream`.

Start the app:

```powershell
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The service binds to your computer only by default. The dashboard continues to show a video preview when no model is installed, but vehicle counts stay at zero.

You can also upload an MP4, MOV, AVI, MKV, or WEBM file from the dashboard. The uploaded file is stored under `media/` and becomes the active analysis source. It remains on your computer and is ignored by Git. Detection requires a compatible `.pt` or `.onnx` model at the path in `MODEL_PATH`.

## Settings

Copy `.env.example` to `.env` and adjust values as needed:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VIDEO_SOURCE` | `media/traffic.mp4` | Local file, `camera`, numeric camera index, or MJPEG URL |
| `MODEL_PATH` | `models/vehicle_detector.pt` | Path to a local YOLOv8 `.pt` or compatible `.onnx` model |
| `CONFIDENCE_THRESHOLD` | `0.40` | Minimum detection confidence |
| `NMS_THRESHOLD` | `0.45` | Non-maximum suppression threshold |
| `CAMERA_INDEX` | `0` | Webcam index when `VIDEO_SOURCE=camera` |
| `FRAME_WIDTH` | `640` | Square model input dimension |

The detector counts cars, motorcycles, buses, and trucks using COCO class IDs. CPU inference is selected by default. Other model families or class orders need an adapter change.

## ESP32-CAM option

1. Open `firmware/esp32cam_stream.ino` in Arduino IDE with the ESP32 board package installed.
2. Select **AI Thinker ESP32-CAM**.
3. Enter your Wi-Fi credentials locally in the sketch. Keep real credentials out of commits.
4. Flash the board and read its stream URL from Serial Monitor.
5. Set `VIDEO_SOURCE` in `.env` to the printed `/stream` URL.

The stream has no authentication. Use it only on a trusted local network.

## Project layout

```text
backend/       FastAPI service, video capture, YOLOv8 detection, timing estimates
dashboard/     Browser dashboard
firmware/      Optional AI Thinker ESP32-CAM MJPEG stream
media/         Local video files (ignored by Git)
models/        Local model weights (ignored by Git)
```

## Licensing and attribution

Copyright (C) 2026 Rohit Basu Roy Chowdhury. The original source files in this repository are licensed under AGPL-3.0; see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The repository does not include the local YOLO weights, reference video, or sample traffic footage. Only include media or model files if you have the rights to redistribute them.
