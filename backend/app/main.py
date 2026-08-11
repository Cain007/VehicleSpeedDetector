from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
import os
import uuid
import shutil
from datetime import datetime

from app.config import settings
from app.database.database import get_db, init_db, close_db
from app.database.models import Video, Calibration, ProcessingJob, VehicleTrack, TrajectoryPoint, GroundTruthValidation
from app.schemas.schemas import (
    VideoUploadResponse, VideoMetadata, CalibrationCreate, CalibrationResponse,
    ProcessingJobStatus, ProcessVideoRequest, VehicleTrackResponse, VideoResults,
    GroundTruthValidationCreate, GroundTruthValidationResponse, ValidationMetrics,
    DashboardStats
)
from app.vision.video.processor import VideoProcessor
from app.workers.video_analyzer import VideoAnalyzer


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="CCTV Vehicle Speed Detection and Analysis System"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    await init_db()
    print(f"Application started: {settings.APP_NAME} v{settings.APP_VERSION}")


@app.on_event("shutdown")
async def shutdown_event():
    await close_db()


# ============ VIDEO ENDPOINTS ============

@app.post("/api/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a CCTV video for processing.
    
    Supported formats: MP4, AVI, MOV, MKV
    Maximum size: 500MB (configurable)
    """
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in settings.SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format. Supported: {', '.join(settings.SUPPORTED_FORMATS)}"
        )
    
    # Generate unique filename
    unique_id = str(uuid.uuid4())
    safe_filename = f"{unique_id}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Extract metadata
    processor = VideoProcessor(file_path)
    if not processor.open():
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Cannot read video file")
    
    metadata = processor.get_metadata()
    processor.close()
    
    if metadata is None:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Invalid video file")
    
    # Create database record
    video = Video(
        filename=file.filename,
        filepath=file_path,
        resolution_width=metadata['width'],
        resolution_height=metadata['height'],
        fps=metadata['fps'],
        duration=metadata['duration'],
        frame_count=metadata['frame_count'],
        processing_status="pending"
    )
    
    db.add(video)
    await db.commit()
    await db.refresh(video)
    
    return VideoUploadResponse(
        id=video.id,
        filename=video.filename,
        filepath=video.filepath,
        resolution_width=video.resolution_width,
        resolution_height=video.resolution_height,
        fps=video.fps,
        duration=video.duration,
        frame_count=video.frame_count,
        processing_status=video.processing_status,
        uploaded_at=video.uploaded_at
    )


@app.get("/api/videos/{video_id}", response_model=VideoMetadata)
async def get_video_metadata(video_id: int, db: AsyncSession = Depends(get_db)):
    """Get video metadata and calibration status."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Check if calibration exists
    cal_result = await db.execute(
        select(Calibration).where(Calibration.video_id == video_id)
    )
    has_calibration = cal_result.scalar_one_or_none() is not None
    
    return VideoMetadata(
        id=video.id,
        filename=video.filename,
        resolution_width=video.resolution_width,
        resolution_height=video.resolution_height,
        fps=video.fps,
        duration=video.duration,
        frame_count=video.frame_count,
        processing_status=video.processing_status,
        uploaded_at=video.uploaded_at,
        has_calibration=has_calibration,
        processed_video_path=video.processed_video_path
    )


@app.get("/api/videos", response_model=List[VideoMetadata])
async def list_videos(db: AsyncSession = Depends(get_db)):
    """List all uploaded videos."""
    result = await db.execute(select(Video).order_by(Video.uploaded_at.desc()))
    videos = result.scalars().all()
    
    return [
        VideoMetadata(
            id=v.id,
            filename=v.filename,
            resolution_width=v.resolution_width,
            resolution_height=v.resolution_height,
            fps=v.fps,
            duration=v.duration,
            frame_count=v.frame_count,
            processing_status=v.processing_status,
            uploaded_at=v.uploaded_at,
            has_calibration=False,  # Would need additional query
            processed_video_path=v.processed_video_path
        )
        for v in videos
    ]


@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a video and all associated data."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete associated files
    try:
        if os.path.exists(video.filepath):
            os.remove(video.filepath)
        if video.processed_video_path and os.path.exists(video.processed_video_path):
            os.remove(video.processed_video_path)
    except Exception as e:
        print(f"Error deleting files: {e}")
    
    # Delete database record (cascade will handle related records)
    await db.delete(video)
    await db.commit()
    
    return {"message": "Video deleted successfully"}


# ============ CALIBRATION ENDPOINTS ============

@app.post("/api/calibration", response_model=CalibrationResponse)
async def save_calibration(
    calibration: CalibrationCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Save calibration points for a video.
    
    Requires at least 4 points for homography calculation.
    """
    if len(calibration.image_points) < 4:
        raise HTTPException(
            status_code=400,
            detail="At least 4 calibration points are required"
        )
    
    # Calculate homography matrix
    from app.vision.calibration.perspective import PerspectiveCalibration
    
    calibrator = PerspectiveCalibration()
    success = calibrator.set_calibration_points(
        calibration.image_points,
        calibration.real_world_points
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to compute homography matrix"
        )
    
    homography_matrix = calibrator.get_homography_matrix()
    
    # Save to database
    db_calibration = Calibration(
        video_id=calibration.video_id,
        image_points=calibration.image_points,
        real_world_points=calibration.real_world_points,
        homography_matrix=homography_matrix,
        is_validated=False
    )
    
    db.add(db_calibration)
    await db.commit()
    await db.refresh(db_calibration)
    
    return CalibrationResponse(
        id=db_calibration.id,
        video_id=db_calibration.video_id,
        image_points=db_calibration.image_points,
        real_world_points=db_calibration.real_world_points,
        homography_matrix=db_calibration.homography_matrix,
        created_at=db_calibration.created_at,
        is_validated=db_calibration.is_validated
    )


@app.get("/api/calibration/{video_id}", response_model=Optional[CalibrationResponse])
async def get_calibration(video_id: int, db: AsyncSession = Depends(get_db)):
    """Get calibration data for a video."""
    result = await db.execute(
        select(Calibration).where(Calibration.video_id == video_id)
    )
    calibration = result.scalar_one_or_none()
    
    if not calibration:
        return None
    
    return CalibrationResponse(
        id=calibration.id,
        video_id=calibration.video_id,
        image_points=calibration.image_points,
        real_world_points=calibration.real_world_points,
        homography_matrix=calibration.homography_matrix,
        created_at=calibration.created_at,
        is_validated=calibration.is_validated
    )


@app.post("/api/calibration/{video_id}/validate")
async def validate_calibration(video_id: int, db: AsyncSession = Depends(get_db)):
    """Mark calibration as validated."""
    result = await db.execute(
        select(Calibration).where(Calibration.video_id == video_id)
    )
    calibration = result.scalar_one_or_none()
    
    if not calibration:
        raise HTTPException(status_code=404, detail="Calibration not found")
    
    calibration.is_validated = True
    await db.commit()
    
    return {"message": "Calibration validated", "video_id": video_id}


# ============ PROCESSING ENDPOINTS ============

@app.post("/api/process")
async def start_processing(
    request: ProcessVideoRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Start video processing job.
    
    This initiates background processing of the video.
    Use GET /api/jobs/{job_id} to check progress.
    """
    # Verify video exists
    result = await db.execute(select(Video).where(Video.id == request.video_id))
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Verify calibration exists
    cal_result = await db.execute(
        select(Calibration).where(Calibration.video_id == request.video_id)
    )
    calibration = cal_result.scalar_one_or_none()
    
    if not calibration:
        raise HTTPException(
            status_code=400,
            detail="Calibration required before processing"
        )
    
    # Create processing job
    job = ProcessingJob(
        video_id=request.video_id,
        status="pending",
        total_frames=video.frame_count
    )
    
    db.add(job)
    await db.commit()
    await db.refresh(job)
    
    # Update video status
    video.processing_status = "processing"
    await db.commit()
    
    # Start background processing
    analyzer = VideoAnalyzer(db)
    background_tasks.add_task(
        analyzer.process_video,
        video_id=video.id,
        job_id=job.id,
        speed_limit=request.speed_limit or settings.SPEED_LIMIT_DEFAULT,
        smoothing_window=request.smoothing_window or settings.SPEED_SMOOTHING_WINDOW
    )
    
    return {"job_id": job.id, "status": "started", "video_id": video.id}


@app.get("/api/jobs/{job_id}", response_model=ProcessingJobStatus)
async def get_job_status(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get processing job status and progress."""
    result = await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return ProcessingJobStatus(
        id=job.id,
        video_id=job.video_id,
        status=job.status,
        progress_percentage=job.progress_percentage,
        current_frame=job.current_frame,
        total_frames=job.total_frames,
        vehicles_detected=job.vehicles_detected,
        vehicles_tracked=job.vehicles_tracked,
        processing_fps=job.processing_fps,
        elapsed_time=job.elapsed_time,
        estimated_remaining_time=job.estimated_remaining_time,
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at
    )


# ============ RESULTS ENDPOINTS ============

@app.get("/api/results/{video_id}", response_model=VideoResults)
async def get_results(video_id: int, db: AsyncSession = Depends(get_db)):
    """Get vehicle detection and speed results for a video."""
    # Get video
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Get all tracks
    tracks_result = await db.execute(
        select(VehicleTrack).where(VehicleTrack.video_id == video_id)
    )
    tracks = tracks_result.scalars().all()
    
    if not tracks:
        return VideoResults(
            video_id=video_id,
            total_vehicles=0,
            average_speed=0.0,
            maximum_speed=0.0,
            overspeed_count=0,
            tracks=[]
        )
    
    # Calculate statistics
    speeds = [t.average_speed_kmh for t in tracks if t.average_speed_kmh]
    max_speeds = [t.maximum_speed_kmh for t in tracks if t.maximum_speed_kmh]
    
    avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
    max_speed = max(max_speeds) if max_speeds else 0.0
    overspeed_count = sum(1 for t in tracks if t.overspeed)
    
    # Get track details with trajectory points
    track_responses = []
    for track in tracks:
        points_result = await db.execute(
            select(TrajectoryPoint)
            .where(TrajectoryPoint.vehicle_track_id == track.id)
            .order_by(TrajectoryPoint.frame_number)
        )
        points = points_result.scalars().all()
        
        track_responses.append(VehicleTrackResponse(
            id=track.id,
            track_id=track.track_id,
            vehicle_type=track.vehicle_type,
            start_time=track.start_time,
            end_time=track.end_time,
            duration_seconds=track.duration_seconds,
            distance_meters=track.distance_meters,
            average_speed_kmh=track.average_speed_kmh,
            maximum_speed_kmh=track.maximum_speed_kmh,
            minimum_speed_kmh=track.minimum_speed_kmh,
            confidence=track.confidence,
            overspeed=track.overspeed,
            trajectory_points=[
                {
                    'frame_number': p.frame_number,
                    'timestamp': p.timestamp,
                    'image_x': p.image_x,
                    'image_y': p.image_y,
                    'world_x': p.world_x,
                    'world_y': p.world_y,
                    'speed_kmh': p.speed_kmh,
                    'smoothed_speed_kmh': p.smoothed_speed_kmh
                }
                for p in points
            ]
        ))
    
    return VideoResults(
        video_id=video_id,
        total_vehicles=len(tracks),
        average_speed=round(avg_speed, 2),
        maximum_speed=round(max_speed, 2),
        overspeed_count=overspeed_count,
        tracks=track_responses
    )


@app.get("/api/download/video/{video_id}")
async def download_processed_video(video_id: int, db: AsyncSession = Depends(get_db)):
    """Download the processed video with overlays."""
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if not video.processed_video_path:
        raise HTTPException(status_code=404, detail="Processed video not available")
    
    if not os.path.exists(video.processed_video_path):
        raise HTTPException(status_code=404, detail="Processed video file not found")
    
    return FileResponse(
        video.processed_video_path,
        media_type="video/mp4",
        filename=f"processed_{video.filename}"
    )


@app.get("/api/download/csv/{video_id}")
async def download_csv_results(video_id: int, db: AsyncSession = Depends(get_db)):
    """Download CSV results file."""
    import csv
    import io
    
    # Get video
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Get all tracks
    tracks_result = await db.execute(
        select(VehicleTrack).where(VehicleTrack.video_id == video_id)
    )
    tracks = tracks_result.scalars().all()
    
    # Generate CSV
    output = io.StringIO()
    fieldnames = [
        'track_id', 'vehicle_type', 'start_timestamp', 'end_timestamp',
        'duration_seconds', 'distance_meters', 'average_speed_kmh',
        'maximum_speed_kmh', 'minimum_speed_kmh', 'confidence', 'overspeed'
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for track in tracks:
        writer.writerow({
            'track_id': track.track_id,
            'vehicle_type': track.vehicle_type,
            'start_timestamp': round(track.start_time, 3),
            'end_timestamp': round(track.end_time, 3),
            'duration_seconds': round(track.duration_seconds, 3),
            'distance_meters': round(track.distance_meters, 2),
            'average_speed_kmh': round(track.average_speed_kmh, 2) if track.average_speed_kmh else '',
            'maximum_speed_kmh': round(track.maximum_speed_kmh, 2) if track.maximum_speed_kmh else '',
            'minimum_speed_kmh': round(track.minimum_speed_kmh, 2) if track.minimum_speed_kmh else '',
            'confidence': round(track.confidence, 3) if track.confidence else '',
            'overspeed': track.overspeed
        })
    
    output.seek(0)
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=results_{video.filename}.csv"
        }
    )


# ============ GROUND TRUTH VALIDATION ENDPOINTS ============

@app.post("/api/validation", response_model=GroundTruthValidationResponse)
async def add_ground_truth_validation(
    validation: GroundTruthValidationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add ground truth validation data for a vehicle track."""
    # Calculate errors
    absolute_error = abs(validation.estimated_speed_kmh - validation.reference_speed_kmh)
    
    if validation.reference_speed_kmh > 0:
        percentage_error = (absolute_error / validation.reference_speed_kmh) * 100
    else:
        percentage_error = 0.0
    
    db_validation = GroundTruthValidation(
        video_id=validation.video_id,
        track_id=validation.track_id,
        reference_speed_kmh=validation.reference_speed_kmh,
        estimated_speed_kmh=validation.estimated_speed_kmh,
        absolute_error=absolute_error,
        percentage_error=percentage_error
    )
    
    db.add(db_validation)
    await db.commit()
    await db.refresh(db_validation)
    
    return GroundTruthValidationResponse(
        id=db_validation.id,
        video_id=db_validation.video_id,
        track_id=db_validation.track_id,
        reference_speed_kmh=db_validation.reference_speed_kmh,
        estimated_speed_kmh=db_validation.estimated_speed_kmh,
        absolute_error=db_validation.absolute_error,
        percentage_error=db_validation.percentage_error
    )


@app.get("/api/validation/{video_id}/metrics", response_model=Optional[ValidationMetrics])
async def get_validation_metrics(video_id: int, db: AsyncSession = Depends(get_db)):
    """Get aggregate validation metrics for a video."""
    result = await db.execute(
        select(GroundTruthValidation).where(GroundTruthValidation.video_id == video_id)
    )
    validations = result.scalars().all()
    
    if not validations:
        return None
    
    absolute_errors = [v.absolute_error for v in validations]
    percentage_errors = [v.percentage_error for v in validations]
    
    mae = sum(absolute_errors) / len(absolute_errors)
    mape = sum(percentage_errors) / len(percentage_errors)
    rmse = np.sqrt(sum(e**2 for e in absolute_errors) / len(absolute_errors))
    mean_error = sum(absolute_errors) / len(absolute_errors)
    std_error = np.std(absolute_errors)
    
    return ValidationMetrics(
        mae=round(mae, 3),
        mape=round(mape, 3),
        rmse=round(rmse, 3),
        mean_error=round(mean_error, 3),
        std_error=round(std_error, 3),
        sample_count=len(validations)
    )


# ============ DASHBOARD ENDPOINTS ============

@app.get("/api/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    # Count processed videos
    result = await db.execute(
        select(func.count(Video.id)).where(Video.processing_status == "completed")
    )
    total_videos = result.scalar() or 0
    
    # Get all vehicle tracks
    tracks_result = await db.execute(select(VehicleTrack))
    tracks = tracks_result.scalars().all()
    
    total_vehicles = len(tracks)
    
    if total_vehicles > 0:
        speeds = [t.average_speed_kmh for t in tracks if t.average_speed_kmh]
        max_speeds = [t.maximum_speed_kmh for t in tracks if t.maximum_speed_kmh]
        
        avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
        max_speed = max(max_speeds) if max_speeds else 0.0
        overspeed_count = sum(1 for t in tracks if t.overspeed)
    else:
        avg_speed = max_speed = 0.0
        overspeed_count = 0
    
    # Get recent jobs
    jobs_result = await db.execute(
        select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(5)
    )
    recent_jobs = jobs_result.scalars().all()
    
    return DashboardStats(
        total_videos_processed=total_videos,
        total_vehicles_detected=total_vehicles,
        average_vehicle_speed=round(avg_speed, 2),
        maximum_detected_speed=round(max_speed, 2),
        overspeed_vehicles_count=overspeed_count,
        recent_jobs=[
            ProcessingJobStatus(
                id=j.id,
                video_id=j.video_id,
                status=j.status,
                progress_percentage=j.progress_percentage,
                current_frame=j.current_frame,
                total_frames=j.total_frames,
                vehicles_detected=j.vehicles_detected,
                vehicles_tracked=j.vehicles_tracked,
                processing_fps=j.processing_fps,
                elapsed_time=j.elapsed_time,
                estimated_remaining_time=j.estimated_remaining_time,
                error_message=j.error_message,
                started_at=j.started_at,
                completed_at=j.completed_at
            )
            for j in recent_jobs
        ]
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


# Import Response for CSV download
from fastapi.responses import Response
import numpy as np
