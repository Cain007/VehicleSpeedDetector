from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "CCTV Vehicle Speed Detection"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./speed_detection.db"
    
    # Storage
    UPLOAD_DIR: str = "./storage/uploads"
    PROCESSED_DIR: str = "./storage/processed"
    FRAMES_DIR: str = "./storage/frames"
    MODELS_DIR: str = "./models"
    
    # Model settings
    TRAFFICCAMNET_MODEL: str = "yolov8n.pt"  # Using YOLOv8 as TrafficCamNet substitute
    DETECTION_CONFIDENCE: float = 0.5
    TRACKING_CONFIDENCE: float = 0.3
    
    # Processing settings
    MAX_VIDEO_SIZE_MB: int = 500
    SUPPORTED_FORMATS: list = [".mp4", ".avi", ".mov", ".mkv"]
    PROCESSING_FPS: Optional[float] = None  # None = use video FPS
    
    # Speed calculation
    SPEED_SMOOTHING_WINDOW: int = 5  # Frames for moving average
    MIN_TRACK_LENGTH: int = 3  # Minimum frames to calculate speed
    SPEED_LIMIT_DEFAULT: float = 60.0  # km/h
    
    # GPU settings
    USE_GPU: bool = True
    GPU_DEVICE: int = 0
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Ensure directories exist
for directory in [settings.UPLOAD_DIR, settings.PROCESSED_DIR, settings.FRAMES_DIR, settings.MODELS_DIR]:
    os.makedirs(directory, exist_ok=True)
