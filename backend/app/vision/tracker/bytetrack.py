import numpy as np
from typing import List, Dict, Any, Optional
from collections import deque


class ByteTrack:
    """
    Multi-object tracker for maintaining vehicle identities across frames.
    Implements a simplified ByteTrack-like approach for tracking vehicles.
    
    Each tracked vehicle receives a persistent ID that is maintained across
    consecutive frames whenever possible.
    """
    
    def __init__(
        self,
        track_thresh: float = 0.5,
        high_thresh: float = 0.6,
        match_thresh: float = 0.8,
        max_age: int = 30,
        min_hits: int = 3
    ):
        """
        Initialize the tracker.
        
        Args:
            track_thresh: Minimum confidence for tracking
            high_thresh: High confidence threshold
            match_thresh: IoU matching threshold
            max_age: Maximum frames to keep track without detection
            min_hits: Minimum detections to confirm track
        """
        self.track_thresh = track_thresh
        self.high_thresh = high_thresh
        self.match_thresh = match_thresh
        self.max_age = max_age
        self.min_hits = min_hits
        
        self.tracks: Dict[int, Track] = {}
        self.next_track_id = 1
    
    def update(self, detections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of detection dictionaries from TrafficCamNet
        
        Returns:
            List of tracked objects with assigned track IDs
        """
        # Separate high and low confidence detections
        high_conf_detections = []
        low_conf_detections = []
        
        for det in detections:
            if det['confidence'] >= self.high_thresh:
                high_conf_detections.append(det)
            elif det['confidence'] >= self.track_thresh:
                low_conf_detections.append(det)
        
        # Get active tracks
        active_tracks = {tid: track for tid, track in self.tracks.items() 
                        if not track.is_dead()}
        
        # First association with high confidence detections
        matched_high, unmatched_high_dets, unmatched_tracks = self._associate(
            list(active_tracks.values()), high_conf_detections
        )
        
        # Second association with low confidence detections
        matched_low, _, _ = self._associate(
            [active_tracks[tid] for tid in unmatched_tracks],
            low_conf_detections,
            track_ids=unmatched_tracks
        )
        
        # Combine matches
        all_matches = matched_high + matched_low
        matched_track_ids = set(m[0] for m in all_matches)
        matched_det_indices = set(m[2] for m in all_matches)
        
        # Update matched tracks
        tracked_objects = []
        for track_id, det, det_idx in all_matches:
            track = self.tracks[track_id]
            track.update(det)
            
            tracked_objects.append({
                'track_id': track_id,
                'detection': det,
                'state': track.get_state()
            })
        
        # Handle unmatched tracks (prediction only)
        for track_id, track in active_tracks.items():
            if track_id not in matched_track_ids:
                track.predict()
                
                if not track.is_dead():
                    tracked_objects.append({
                        'track_id': track_id,
                        'detection': None,
                        'state': track.get_state()
                    })
        
        # Create new tracks for unmatched detections
        for i, det in enumerate(detections):
            if i not in matched_det_indices and det['confidence'] >= self.high_thresh:
                track = Track(self.next_track_id, det)
                self.tracks[self.next_track_id] = track
                self.next_track_id += 1
                
                tracked_objects.append({
                    'track_id': track.track_id,
                    'detection': det,
                    'state': track.get_state()
                })
        
        return tracked_objects
    
    def _associate(
        self,
        tracks: List['Track'],
        detections: List[Dict[str, Any]],
        track_ids: Optional[List[int]] = None
    ) -> tuple:
        """
        Associate tracks with detections using IoU matching.
        
        Returns:
            Tuple of (matches, unmatched_detections, unmatched_tracks)
        """
        if track_ids is None:
            track_ids = [t.track_id for t in tracks]
        
        matches = []
        unmatched_dets = list(range(len(detections)))
        unmatched_tracks = list(track_ids)
        
        if len(tracks) == 0 or len(detections) == 0:
            return matches, unmatched_dets, unmatched_tracks
        
        # Build cost matrix (1 - IoU)
        cost_matrix = np.zeros((len(tracks), len(detections)))
        
        for i, track in enumerate(tracks):
            for j, det in enumerate(detections):
                iou = self._calculate_iou(track.get_position(), det['bbox'])
                cost_matrix[i, j] = 1 - iou
        
        # Greedy matching
        while True:
            if cost_matrix.size == 0:
                break
            
            # Find minimum cost
            min_cost_idx = np.unravel_index(np.argmin(cost_matrix), cost_matrix.shape)
            min_cost = cost_matrix[min_cost_idx]
            
            if min_cost > (1 - self.match_thresh):
                break
            
            track_idx, det_idx = min_cost_idx
            track_id = track_ids[track_idx]
            
            matches.append((track_id, tracks[track_idx], det_idx))
            unmatched_dets.remove(det_idx)
            unmatched_tracks.remove(track_id)
            
            # Remove matched row and column
            cost_matrix = np.delete(cost_matrix, track_idx, axis=0)
            cost_matrix = np.delete(cost_matrix, det_idx, axis=1)
            tracks.pop(track_idx)
            track_ids.pop(track_idx)
        
        return matches, unmatched_dets, unmatched_tracks
    
    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate Intersection over Union between two bounding boxes."""
        x1, y1, x2, y2 = bbox1
        x3, y3, x4, y4 = bbox2
        
        # Calculate intersection
        xi1 = max(x1, x3)
        yi1 = max(y1, y3)
        xi2 = min(x2, x4)
        yi2 = min(y2, y4)
        
        inter_w = max(0, xi2 - xi1)
        inter_h = max(0, yi2 - yi1)
        inter_area = inter_w * inter_h
        
        # Calculate union
        area1 = (x2 - x1) * (y2 - y1)
        area2 = (x4 - x3) * (y4 - y3)
        union_area = area1 + area2 - inter_area
        
        if union_area == 0:
            return 0
        
        return inter_area / union_area
    
    def get_all_tracks(self) -> List[Dict[str, Any]]:
        """Get all active tracks."""
        return [
            {
                'track_id': track.track_id,
                'vehicle_type': track.vehicle_type,
                'state': track.get_state(),
                'age': track.age,
                'hits': track.hits
            }
            for track in self.tracks.values()
            if not track.is_dead()
        ]


class Track:
    """Represents a single tracked vehicle."""
    
    def __init__(self, track_id: int, detection: Dict[str, Any]):
        self.track_id = track_id
        self.vehicle_type = detection['class_name']
        self.confidence = detection['confidence']
        
        # Bounding box state
        self.bbox = detection['bbox'].copy()
        self.bottom_center = detection['bottom_center']
        
        # Kalman filter-like state (simplified)
        self.velocity = np.zeros(2)  # (vx, vy)
        self.position_history = deque(maxlen=30)
        self.position_history.append(self.bottom_center)
        
        # Track management
        self.age = 1
        self.hits = 1
        self.time_since_update = 0
    
    def update(self, detection: Dict[str, Any]):
        """Update track with new detection."""
        self.bbox = detection['bbox'].copy()
        self.bottom_center = detection['bottom_center']
        self.confidence = detection['confidence']
        self.vehicle_type = detection['class_name']
        
        # Update velocity
        if len(self.position_history) > 0:
            prev_pos = np.array(self.position_history[-1])
            curr_pos = np.array(self.bottom_center)
            self.velocity = curr_pos - prev_pos
        
        self.position_history.append(self.bottom_center)
        self.hits += 1
        self.time_since_update = 0
        self.age += 1
    
    def predict(self):
        """Predict next position (when no detection available)."""
        # Simple linear prediction
        predicted_pos = np.array(self.bottom_center) + self.velocity
        self.bottom_center = (float(predicted_pos[0]), float(predicted_pos[1]))
        self.time_since_update += 1
        self.age += 1
    
    def get_position(self) -> List[float]:
        """Get current bounding box position."""
        return self.bbox.copy()
    
    def get_state(self) -> Dict[str, Any]:
        """Get current track state."""
        return {
            'bbox': self.bbox,
            'bottom_center': self.bottom_center,
            'velocity': self.velocity.tolist(),
            'vehicle_type': self.vehicle_type,
            'confidence': self.confidence
        }
    
    def is_dead(self) -> bool:
        """Check if track should be terminated."""
        return self.time_since_update > 30 or (self.age < self.min_hits and self.time_since_update > 3)
    
    @property
    def min_hits(self) -> int:
        return 3
