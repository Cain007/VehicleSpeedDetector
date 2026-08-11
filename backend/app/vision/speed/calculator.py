import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from collections import deque


class SpeedCalculator:
    """
    Calculates vehicle speed from trajectory points using real-world coordinates.
    
    Implements speed smoothing and distinguishes between:
    - Instantaneous speed (frame-by-frame)
    - Smoothed speed (moving average)
    - Average speed (over entire track)
    - Maximum/Minimum speed
    """
    
    def __init__(self, smoothing_window: int = 5):
        """
        Initialize speed calculator.
        
        Args:
            smoothing_window: Number of frames for moving average smoothing
        """
        self.smoothing_window = smoothing_window
    
    def calculate_speed(
        self,
        trajectory_points: List[Dict[str, Any]],
        fps: float
    ) -> List[Dict[str, Any]]:
        """
        Calculate speeds for all points in a trajectory.
        
        Args:
            trajectory_points: List of trajectory point dictionaries with world coordinates
            fps: Video frames per second
        
        Returns:
            Updated trajectory points with speed information
        """
        if len(trajectory_points) < 2:
            return trajectory_points
        
        # Calculate instantaneous speeds
        speeds = []
        for i in range(len(trajectory_points)):
            if i == 0:
                speeds.append(0.0)
            else:
                prev_point = trajectory_points[i - 1]
                curr_point = trajectory_points[i]
                
                if prev_point.get('world_x') is not None and curr_point.get('world_x') is not None:
                    # Calculate distance in real-world meters
                    dx = curr_point['world_x'] - prev_point['world_x']
                    dy = curr_point['world_y'] - prev_point['world_y']
                    distance = np.sqrt(dx**2 + dy**2)
                    
                    # Time between frames
                    dt = 1.0 / fps
                    
                    # Speed in m/s, then convert to km/h
                    speed_mps = distance / dt
                    speed_kmh = speed_mps * 3.6
                    
                    speeds.append(speed_kmh)
                else:
                    speeds.append(None)
        
        # Apply smoothing
        smoothed_speeds = self._apply_smoothing(speeds)
        
        # Update trajectory points with speeds
        for i, point in enumerate(trajectory_points):
            point['speed_kmh'] = speeds[i]
            point['smoothed_speed_kmh'] = smoothed_speeds[i]
        
        return trajectory_points
    
    def _apply_smoothing(self, speeds: List[Optional[float]]) -> List[Optional[float]]:
        """
        Apply moving average smoothing to speed values.
        
        Args:
            speeds: List of speed values (may contain None)
        
        Returns:
            List of smoothed speed values
        """
        smoothed = []
        
        for i in range(len(speeds)):
            if speeds[i] is None:
                smoothed.append(None)
                continue
            
            # Collect valid speeds in window
            window_start = max(0, i - self.smoothing_window + 1)
            window_speeds = [s for s in speeds[window_start:i+1] if s is not None]
            
            if len(window_speeds) > 0:
                smoothed.append(np.mean(window_speeds))
            else:
                smoothed.append(None)
        
        return smoothed
    
    def calculate_track_statistics(
        self,
        trajectory_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate overall statistics for a vehicle track.
        
        Args:
            trajectory_points: List of trajectory points with speed information
        
        Returns:
            Dictionary containing track statistics
        """
        if len(trajectory_points) < 2:
            return {
                'distance_meters': 0.0,
                'average_speed_kmh': 0.0,
                'maximum_speed_kmh': 0.0,
                'minimum_speed_kmh': 0.0,
                'duration_seconds': 0.0
            }
        
        # Filter valid world coordinates
        valid_points = [p for p in trajectory_points 
                       if p.get('world_x') is not None and p.get('world_y') is not None]
        
        if len(valid_points) < 2:
            return {
                'distance_meters': 0.0,
                'average_speed_kmh': 0.0,
                'maximum_speed_kmh': 0.0,
                'minimum_speed_kmh': 0.0,
                'duration_seconds': 0.0
            }
        
        # Calculate total distance
        total_distance = 0.0
        for i in range(1, len(valid_points)):
            prev = valid_points[i - 1]
            curr = valid_points[i]
            dx = curr['world_x'] - prev['world_x']
            dy = curr['world_y'] - prev['world_y']
            total_distance += np.sqrt(dx**2 + dy**2)
        
        # Calculate duration
        start_time = valid_points[0].get('timestamp', 0)
        end_time = valid_points[-1].get('timestamp', 0)
        duration = end_time - start_time
        
        # Calculate speed statistics
        valid_speeds = [p.get('smoothed_speed_kmh') for p in trajectory_points 
                       if p.get('smoothed_speed_kmh') is not None]
        
        if len(valid_speeds) > 0:
            avg_speed = np.mean(valid_speeds)
            max_speed = np.max(valid_speeds)
            min_speed = np.min(valid_speeds)
        else:
            avg_speed = max_speed = min_speed = 0.0
        
        # If we have duration, recalculate average speed from distance/time
        if duration > 0:
            avg_speed_from_distance = (total_distance / duration) * 3.6  # Convert m/s to km/h
            # Use the more accurate measure
            avg_speed = avg_speed_from_distance
        
        return {
            'distance_meters': round(total_distance, 2),
            'average_speed_kmh': round(avg_speed, 2),
            'maximum_speed_kmh': round(max_speed, 2),
            'minimum_speed_kmh': round(min_speed, 2),
            'duration_seconds': round(duration, 3)
        }
    
    def exponential_moving_average(
        self,
        speeds: List[Optional[float]],
        alpha: float = 0.3
    ) -> List[Optional[float]]:
        """
        Apply exponential moving average smoothing.
        
        Args:
            speeds: List of speed values
            alpha: Smoothing factor (0 < alpha < 1)
        
        Returns:
            List of EMA-smoothed speeds
        """
        if len(speeds) == 0:
            return []
        
        smoothed = []
        ema = None
        
        for speed in speeds:
            if speed is None:
                smoothed.append(None)
                continue
            
            if ema is None:
                ema = speed
            else:
                ema = alpha * speed + (1 - alpha) * ema
            
            smoothed.append(ema)
        
        return smoothed


class VehicleTracker:
    """
    Maintains complete tracking information for each vehicle including
    trajectory points and calculated speeds.
    """
    
    def __init__(self, track_id: int, vehicle_type: str, confidence: float):
        self.track_id = track_id
        self.vehicle_type = vehicle_type
        self.confidence = confidence
        self.trajectory_points: List[Dict[str, Any]] = []
        self.is_complete = False
    
    def add_point(
        self,
        frame_number: int,
        timestamp: float,
        image_x: float,
        image_y: float,
        bbox: List[float],
        world_x: Optional[float] = None,
        world_y: Optional[float] = None
    ):
        """Add a trajectory point."""
        self.trajectory_points.append({
            'frame_number': frame_number,
            'timestamp': timestamp,
            'image_x': image_x,
            'image_y': image_y,
            'world_x': world_x,
            'world_y': world_y,
            'bbox_x': bbox[0],
            'bbox_y': bbox[1],
            'bbox_width': bbox[2] - bbox[0],
            'bbox_height': bbox[3] - bbox[1]
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get track summary."""
        if len(self.trajectory_points) > 0:
            start_time = self.trajectory_points[0]['timestamp']
            end_time = self.trajectory_points[-1]['timestamp']
        else:
            start_time = end_time = 0
        
        return {
            'track_id': self.track_id,
            'vehicle_type': self.vehicle_type,
            'start_time': start_time,
            'end_time': end_time,
            'point_count': len(self.trajectory_points),
            'is_complete': self.is_complete
        }
