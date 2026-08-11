import asyncio
import time
import cv2
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
from datetime import datetime

from app.database.models import (
    Video, Calibration, ProcessingJob, VehicleTrack, TrajectoryPoint
)
from app.vision.video.processor import VideoProcessor
from app.vision.detector.trafficcamnet import TrafficCamNet
from app.vision.tracker.bytetrack import ByteTrack
from app.vision.calibration.perspective import PerspectiveCalibration
from app.vision.speed.calculator import SpeedCalculator, VehicleTracker
from app.config import settings


class VideoAnalyzer:
    """
    Background worker for processing CCTV videos.
    
    Pipeline:
    1. Load video and calibration
    2. Initialize detector (TrafficCamNet) and tracker
    3. Process each frame:
       - Detect vehicles
       - Update tracks
       - Transform positions to world coordinates
       - Calculate speeds
    4. Generate annotated output video
    5. Save results to database
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.detector: Optional[TrafficCamNet] = None
        self.tracker: Optional[ByteTrack] = None
        self.calibrator: Optional[PerspectiveCalibration] = None
        self.speed_calculator: Optional[SpeedCalculator] = None
        
        # Active vehicle tracks
        self.active_tracks: Dict[int, VehicleTracker] = {}
        self.completed_tracks: list = []
        
        # Processing statistics
        self.start_time: float = 0
        self.frames_processed: int = 0
        self.detection_count: int = 0
    
    async def process_video(
        self,
        video_id: int,
        job_id: int,
        speed_limit: float,
        smoothing_window: int
    ):
        """Main processing function run in background."""
        try:
            self.start_time = time.time()
            
            # Update job status to running
            await self._update_job_status(job_id, "running", 0)
            
            # Load video from database
            result = await self.db.execute(select(Video).where(Video.id == video_id))
            video = result.scalar_one_or_none()
            
            if not video:
                raise Exception(f"Video {video_id} not found")
            
            # Load calibration
            cal_result = await self.db.execute(
                select(Calibration).where(Calibration.video_id == video_id)
            )
            calibration = cal_result.scalar_one_or_none()
            
            if not calibration:
                raise Exception("No calibration found for video")
            
            # Initialize components
            self.detector = TrafficCamNet(
                model_path=settings.TRAFFICCAMNET_MODEL,
                use_gpu=settings.USE_GPU
            )
            
            self.tracker = ByteTrack()
            
            self.calibrator = PerspectiveCalibration()
            self.calibrator.set_calibration_points(
                calibration.image_points,
                calibration.real_world_points
            )
            
            self.speed_calculator = SpeedCalculator(smoothing_window=smoothing_window)
            
            # Open video processor
            processor = VideoProcessor(video.filepath)
            if not processor.open():
                raise Exception("Cannot open video file")
            
            metadata = processor.get_metadata()
            total_frames = metadata['frame_count']
            fps = metadata['fps']
            
            # Create output video writer
            output_path = f"{settings.PROCESSED_DIR}/processed_{video_id}.mp4"
            writer = processor.create_video_writer(output_path)
            
            if not writer:
                raise Exception("Cannot create output video writer")
            
            # Process frames
            frame_number = 0
            
            for frame_num, frame in processor.iterate_frames():
                try:
                    # Run detection
                    detections = self.detector.detect(frame, settings.DETECTION_CONFIDENCE)
                    self.detection_count += len(detections)
                    
                    # Update tracking
                    tracked_objects = self.tracker.update(detections)
                    
                    # Process each tracked object
                    timestamp = frame_num / fps
                    
                    for obj in tracked_objects:
                        track_id = obj['track_id']
                        det = obj['detection']
                        state = obj['state']
                        
                        if det is None:
                            continue
                        
                        # Get bottom-center position
                        bottom_center = det['bottom_center']
                        
                        # Transform to world coordinates
                        world_pos = self.calibrator.image_to_world(
                            bottom_center[0],
                            bottom_center[1]
                        )
                        
                        world_x, world_y = world_pos if world_pos else (None, None)
                        
                        # Get or create vehicle tracker
                        if track_id not in self.active_tracks:
                            self.active_tracks[track_id] = VehicleTracker(
                                track_id=track_id,
                                vehicle_type=det['class_name'],
                                confidence=det['confidence']
                            )
                        
                        # Add trajectory point
                        self.active_tracks[track_id].add_point(
                            frame_number=frame_num,
                            timestamp=timestamp,
                            image_x=bottom_center[0],
                            image_y=bottom_center[1],
                            bbox=det['bbox'],
                            world_x=world_x,
                            world_y=world_y
                        )
                    
                    # Calculate speeds for active tracks
                    for track in self.active_tracks.values():
                        if len(track.trajectory_points) >= 2:
                            track.trajectory_points = self.speed_calculator.calculate_speed(
                                track.trajectory_points,
                                fps
                            )
                    
                    # Check for completed tracks (not seen recently)
                    completed_track_ids = []
                    for track_id, track in self.active_tracks.items():
                        last_point = track.trajectory_points[-1] if track.trajectory_points else None
                        if last_point and (frame_num - last_point['frame_number']) > 30:
                            # Track is complete
                            track.is_complete = True
                            self.completed_tracks.append(track)
                            completed_track_ids.append(track_id)
                    
                    for track_id in completed_track_ids:
                        del self.active_tracks[track_id]
                    
                    # Draw overlays on frame
                    annotated_frame = self._draw_overlays(
                        frame,
                        tracked_objects,
                        speed_limit
                    )
                    
                    # Write frame
                    writer.write(annotated_frame)
                    
                    # Update progress
                    self.frames_processed = frame_num + 1
                    progress = (self.frames_processed / total_frames) * 100
                    
                    elapsed = time.time() - self.start_time
                    processing_fps = self.frames_processed / elapsed if elapsed > 0 else 0
                    remaining_frames = total_frames - self.frames_processed
                    eta = remaining_frames / processing_fps if processing_fps > 0 else 0
                    
                    await self._update_job_status(
                        job_id,
                        "running",
                        progress,
                        current_frame=self.frames_processed,
                        vehicles_detected=self.detection_count,
                        vehicles_tracked=len(self.active_tracks) + len(self.completed_tracks),
                        processing_fps=processing_fps,
                        elapsed_time=elapsed,
                        estimated_remaining_time=eta
                    )
                    
                except Exception as e:
                    print(f"Error processing frame {frame_num}: {e}")
                    continue
            
            # Finalize remaining tracks
            for track in self.active_tracks.values():
                track.is_complete = True
                self.completed_tracks.append(track)
            
            self.active_tracks.clear()
            
            # Close resources
            writer.release()
            processor.close()
            
            # Save results to database
            await self._save_results(video_id, speed_limit)
            
            # Update video record
            video.processing_status = "completed"
            video.processed_video_path = output_path
            await self.db.commit()
            
            # Mark job as completed
            elapsed = time.time() - self.start_time
            await self._update_job_status(
                job_id,
                "completed",
                100,
                current_frame=total_frames,
                vehicles_detected=self.detection_count,
                vehicles_tracked=len(self.completed_tracks),
                elapsed_time=elapsed
            )
            
            print(f"Processing completed for video {video_id}")
            
        except Exception as e:
            print(f"Processing failed: {e}")
            await self._update_job_status(job_id, "failed", 0, error_message=str(e))
            
            # Update video status
            result = await self.db.execute(select(Video).where(Video.id == video_id))
            video = result.scalar_one_or_none()
            if video:
                video.processing_status = "failed"
                await self.db.commit()
    
    def _draw_overlays(
        self,
        frame: np.ndarray,
        tracked_objects: list,
        speed_limit: float
    ) -> np.ndarray:
        """Draw bounding boxes, IDs, and speeds on frame."""
        overlay = frame.copy()
        
        for obj in tracked_objects:
            det = obj['detection']
            if det is None:
                continue
            
            track_id = obj['track_id']
            bbox = det['bbox']
            class_name = det['class_name']
            
            # Get current speed from active track
            speed_kmh = 0.0
            if track_id in self.active_tracks:
                track = self.active_tracks[track_id]
                if track.trajectory_points:
                    last_point = track.trajectory_points[-1]
                    speed_kmh = last_point.get('smoothed_speed_kmh', 0.0) or 0.0
            
            # Determine color based on speed
            if speed_kmh > speed_limit:
                color = (0, 0, 255)  # Red for overspeed
            elif speed_kmh > speed_limit * 0.8:
                color = (0, 255, 255)  # Yellow for near limit
            else:
                color = (0, 255, 0)  # Green for normal
            
            # Draw bounding box
            x1, y1, x2, y2 = map(int, bbox)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
            
            # Draw label
            label = f"{class_name.upper()} #{track_id}"
            speed_label = f"{speed_kmh:.1f} km/h"
            
            # Background for text
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(
                overlay,
                (x1, y1 - text_size[1] - 25),
                (x1 + text_size[0], y1),
                color,
                -1
            )
            
            # Text
            cv2.putText(
                overlay,
                label,
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )
            
            cv2.putText(
                overlay,
                speed_label,
                (x1, y1 + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )
            
            # Draw trajectory history
            if track_id in self.active_tracks:
                track = self.active_tracks[track_id]
                points = track.trajectory_points
                
                if len(points) > 1:
                    trail_points = []
                    for p in points[-20:]:  # Last 20 points
                        if p.get('image_x') is not None:
                            trail_points.append((int(p['image_x']), int(p['image_y'])))
                    
                    if len(trail_points) > 1:
                        for i in range(1, len(trail_points)):
                            alpha = i / len(trail_points)
                            trail_color = (
                                int(color[0] * alpha),
                                int(color[1] * alpha),
                                int(color[2] * alpha)
                            )
                            cv2.line(
                                overlay,
                                trail_points[i-1],
                                trail_points[i],
                                trail_color,
                                2
                            )
        
        return overlay
    
    async def _save_results(self, video_id: int, speed_limit: float):
        """Save completed tracks to database."""
        for track in self.completed_tracks:
            if len(track.trajectory_points) < 2:
                continue
            
            # Calculate statistics
            stats = self.speed_calculator.calculate_track_statistics(
                track.trajectory_points
            )
            
            # Check if overspeed
            overspeed = stats['maximum_speed_kmh'] > speed_limit
            
            # Create vehicle track record
            db_track = VehicleTrack(
                video_id=video_id,
                track_id=track.track_id,
                vehicle_type=track.vehicle_type,
                start_time=track.trajectory_points[0]['timestamp'],
                end_time=track.trajectory_points[-1]['timestamp'],
                duration_seconds=stats['duration_seconds'],
                distance_meters=stats['distance_meters'],
                average_speed_kmh=stats['average_speed_kmh'],
                maximum_speed_kmh=stats['maximum_speed_kmh'],
                minimum_speed_kmh=stats['minimum_speed_kmh'],
                confidence=track.confidence,
                overspeed=overspeed
            )
            
            self.db.add(db_track)
            await self.db.flush()
            
            # Create trajectory points
            for point in track.trajectory_points:
                db_point = TrajectoryPoint(
                    vehicle_track_id=db_track.id,
                    frame_number=point['frame_number'],
                    timestamp=point['timestamp'],
                    image_x=point['image_x'],
                    image_y=point['image_y'],
                    world_x=point.get('world_x'),
                    world_y=point.get('world_y'),
                    speed_kmh=point.get('speed_kmh'),
                    smoothed_speed_kmh=point.get('smoothed_speed_kmh'),
                    bbox_x=point.get('bbox_x'),
                    bbox_y=point.get('bbox_y'),
                    bbox_width=point.get('bbox_width'),
                    bbox_height=point.get('bbox_height')
                )
                self.db.add(db_point)
        
        await self.db.commit()
    
    async def _update_job_status(
        self,
        job_id: int,
        status: str,
        progress: float,
        **kwargs
    ):
        """Update processing job status in database."""
        result = await self.db.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        
        if not job:
            return
        
        job.status = status
        job.progress_percentage = progress
        
        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)
        
        if status == "running" and not job.started_at:
            job.started_at = datetime.utcnow()
        elif status in ["completed", "failed"]:
            job.completed_at = datetime.utcnow()
        
        await self.db.commit()
