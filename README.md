# CCTV Vehicle Speed Detection System

A full-stack web application for detecting, tracking, and estimating vehicle speeds from CCTV footage.

## Features

- Upload CCTV videos (MP4, AVI, MOV, MKV)
- Interactive road calibration with perspective transformation
- Vehicle detection using TrafficCamNet
- Multi-object tracking with persistent IDs
- Real-world speed estimation in km/h
- Speed smoothing algorithms
- Annotated video export
- CSV results export
- Ground-truth validation metrics

## Architecture

```
Frontend (React + TypeScript + Tailwind CSS)
    ↓
Backend (FastAPI + Python)
    ↓
Video Processing Pipeline:
    - Video Decoder
    - TrafficCamNet Detector
    - Multi-Object Tracker
    - Perspective Transformation
    - Speed Calculation
```

## Project Structure

```
/workspace
├── frontend/          # React TypeScript application
├── backend/           # FastAPI backend
│   └── app/
│       ├── api/       # REST endpoints
│       ├── services/  # Business logic
│       ├── models/    # Database models
│       ├── schemas/   # Pydantic schemas
│       ├── workers/   # Background processing
│       ├── vision/    # Computer vision modules
│       │   ├── detector/   # TrafficCamNet
│       │   ├── tracker/    # Multi-object tracking
│       │   ├── calibration/# Homography calculation
│       │   └── speed/      # Speed estimation
│       └── database/  # SQLite database
├── storage/           # Uploaded and processed files
├── models/            # AI model weights
└── tests/             # Test suite
```

## Quick Start

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

## Usage

1. Open the web application
2. Upload a traffic video
3. Select 4+ road reference points for calibration
4. Enter real-world measurements
5. Start analysis
6. View results and download outputs

## API Endpoints

- `POST /api/upload` - Upload video
- `GET /api/videos/{id}` - Get video metadata
- `POST /api/calibration` - Save calibration points
- `POST /api/process/{video_id}` - Start processing
- `GET /api/jobs/{job_id}` - Get processing status
- `GET /api/results/{video_id}` - Get vehicle results
- `GET /api/download/video/{video_id}` - Download processed video
- `GET /api/download/csv/{video_id}` - Download CSV results

## Requirements

- Python 3.9+
- Node.js 18+
- NVIDIA GPU (optional, for acceleration)
- OpenCV
- PyTorch

## License

MIT License - For educational/research purposes
