from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# Video schemas
class VideoBase(BaseModel):
    filename: str
    filepath: str


class VideoUploadResponse(VideoBase):
    id: int
    resolution_width: int
    resolution_height: int
    fps: float
    duration: float
    frame_count: int
    processing_status: str
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


class VideoMetadata(BaseModel):
    id: int
    filename: str
    resolution_width: int
    resolution_height: int
    fps: float
    duration: float
    frame_count: int
    processing_status: str
    uploaded_at: datetime
    has_calibration: bool = False
    processed_video_path: Optional[str] = None
    
    class Config:
        from_attributes = True


# Calibration schemas
class CalibrationCreate(BaseModel):
    video_id: int
    image_points: List[List[float]]  # [[x1,y1], [x2,y2], ...]
    real_world_points: List[List[float]]  # [[x1,y1], [x2,y2], ...] in meters


class CalibrationResponse(BaseModel):
    id: int
    video_id: int
    image_points: List[List[float]]
    real_world_points: List[List[float]]
    homography_matrix: Optional[List[List[float]]]
    created_at: datetime
    is_validated: bool
    
    class Config:
        from_attributes = True


# Processing job schemas
class ProcessingJobStatus(BaseModel):
    id: int
    video_id: int
    status: str
    progress_percentage: float
    current_frame: int
    total_frames: int
    vehicles_detected: int
    vehicles_tracked: int
    processing_fps: Optional[float]
    elapsed_time: Optional[float]
    estimated_remaining_time: Optional[float]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ProcessVideoRequest(BaseModel):
    video_id: int
    speed_limit: Optional[float] = 60.0
    smoothing_window: Optional[int] = 5


# Vehicle track schemas
class TrajectoryPointSchema(BaseModel):
    frame_number: int
    timestamp: float
    image_x: float
    image_y: float
    world_x: Optional[float]
    world_y: Optional[float]
    speed_kmh: Optional[float]
    smoothed_speed_kmh: Optional[float]
    
    class Config:
        from_attributes = True


class VehicleTrackResponse(BaseModel):
    id: int
    track_id: int
    vehicle_type: str
    start_time: float
    end_time: float
    duration_seconds: float
    distance_meters: float
    average_speed_kmh: float
    maximum_speed_kmh: float
    minimum_speed_kmh: float
    confidence: float
    overspeed: bool
    trajectory_points: Optional[List[TrajectoryPointSchema]] = None
    
    class Config:
        from_attributes = True


# Results schema
class VideoResults(BaseModel):
    video_id: int
    total_vehicles: int
    average_speed: float
    maximum_speed: float
    overspeed_count: int
    tracks: List[VehicleTrackResponse]


# Ground truth validation schema
class GroundTruthValidationCreate(BaseModel):
    video_id: int
    track_id: int
    reference_speed_kmh: float
    estimated_speed_kmh: float


class GroundTruthValidationResponse(BaseModel):
    id: int
    video_id: int
    track_id: int
    reference_speed_kmh: float
    estimated_speed_kmh: float
    absolute_error: float
    percentage_error: float
    
    class Config:
        from_attributes = True


class ValidationMetrics(BaseModel):
    mae: float  # Mean Absolute Error
    mape: float  # Mean Absolute Percentage Error
    rmse: float  # Root Mean Square Error
    mean_error: float
    std_error: float
    sample_count: int


# Dashboard stats schema
class DashboardStats(BaseModel):
    total_videos_processed: int
    total_vehicles_detected: int
    average_vehicle_speed: float
    maximum_detected_speed: float
    overspeed_vehicles_count: int
    recent_jobs: List[ProcessingJobStatus]
