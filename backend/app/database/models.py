from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Video(Base):
    __tablename__ = "videos"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    resolution_width = Column(Integer)
    resolution_height = Column(Integer)
    fps = Column(Float)
    duration = Column(Float)  # in seconds
    frame_count = Column(Integer)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    processed_video_path = Column(String, nullable=True)
    
    # Relationships
    calibrations = relationship("Calibration", back_populates="video", cascade="all, delete-orphan")
    vehicle_tracks = relationship("VehicleTrack", back_populates="video", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="video", cascade="all, delete-orphan")


class Calibration(Base):
    __tablename__ = "calibrations"
    
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    image_points = Column(JSON, nullable=False)  # [[x1,y1], [x2,y2], ...]
    real_world_points = Column(JSON, nullable=False)  # [[x1,y1], [x2,y2], ...] in meters
    homography_matrix = Column(JSON, nullable=True)  # 3x3 matrix as nested list
    created_at = Column(DateTime, default=datetime.utcnow)
    is_validated = Column(Boolean, default=False)
    
    # Relationship
    video = relationship("Video", back_populates="calibrations")


class VehicleTrack(Base):
    __tablename__ = "vehicle_tracks"
    
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    track_id = Column(Integer, nullable=False)
    vehicle_type = Column(String, nullable=False)  # car, two-wheeler, etc.
    start_time = Column(Float)  # timestamp in seconds
    end_time = Column(Float)
    duration_seconds = Column(Float)
    distance_meters = Column(Float)
    average_speed_kmh = Column(Float)
    maximum_speed_kmh = Column(Float)
    minimum_speed_kmh = Column(Float)
    confidence = Column(Float)
    overspeed = Column(Boolean, default=False)
    
    # Relationship
    video = relationship("Video", back_populates="vehicle_tracks")
    trajectory_points = relationship("TrajectoryPoint", back_populates="vehicle_track", cascade="all, delete-orphan")


class TrajectoryPoint(Base):
    __tablename__ = "trajectory_points"
    
    id = Column(Integer, primary_key=True, index=True)
    vehicle_track_id = Column(Integer, ForeignKey("vehicle_tracks.id"), nullable=False)
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    image_x = Column(Float, nullable=False)
    image_y = Column(Float, nullable=False)
    world_x = Column(Float, nullable=True)  # Real-world position in meters
    world_y = Column(Float, nullable=True)
    speed_kmh = Column(Float, nullable=True)
    smoothed_speed_kmh = Column(Float, nullable=True)
    bbox_x = Column(Float)  # Bounding box coordinates
    bbox_y = Column(Float)
    bbox_width = Column(Float)
    bbox_height = Column(Float)
    
    # Relationship
    vehicle_track = relationship("VehicleTrack", back_populates="trajectory_points")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    status = Column(String, default="pending")  # pending, running, completed, failed
    progress_percentage = Column(Float, default=0.0)
    current_frame = Column(Integer, default=0)
    total_frames = Column(Integer)
    vehicles_detected = Column(Integer, default=0)
    vehicles_tracked = Column(Integer, default=0)
    processing_fps = Column(Float, nullable=True)
    elapsed_time = Column(Float, nullable=True)
    estimated_remaining_time = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    video = relationship("Video", back_populates="processing_jobs")


class GroundTruthValidation(Base):
    __tablename__ = "ground_truth_validations"
    
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    track_id = Column(Integer, nullable=False)
    reference_speed_kmh = Column(Float, nullable=False)
    estimated_speed_kmh = Column(Float, nullable=False)
    absolute_error = Column(Float)
    percentage_error = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
