import cv2
import numpy as np
from typing import Optional, Dict, Any, Tuple
from pathlib import Path


class VideoProcessor:
    """
    Handles video file operations including reading metadata,
    extracting frames, and writing processed videos.
    """
    
    def __init__(self, video_path: str):
        """
        Initialize video processor.
        
        Args:
            video_path: Path to the video file
        """
        self.video_path = video_path
        self.cap: Optional[cv2.VideoCapture] = None
        self._metadata: Optional[Dict[str, Any]] = None
    
    def open(self) -> bool:
        """Open the video file."""
        try:
            self.cap = cv2.VideoCapture(self.video_path)
            return self.cap.isOpened()
        except Exception as e:
            print(f"Error opening video: {e}")
            return False
    
    def close(self):
        """Close the video file."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
    
    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Extract video metadata.
        
        Returns:
            Dictionary containing video metadata or None if failed
        """
        if self._metadata is not None:
            return self._metadata
        
        if self.cap is None:
            if not self.open():
                return None
        
        try:
            width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(self.cap.get(cv2.CAP_PROP_FPS))
            frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Calculate duration
            duration = frame_count / fps if fps > 0 else 0
            
            # Get codec info
            fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
            codec_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
            
            self._metadata = {
                'width': width,
                'height': height,
                'fps': fps,
                'frame_count': frame_count,
                'duration': duration,
                'codec': codec_str,
                'path': self.video_path
            }
            
            return self._metadata
        
        except Exception as e:
            print(f"Error getting metadata: {e}")
            return None
    
    def get_frame(self, frame_number: int) -> Optional[np.ndarray]:
        """
        Get a specific frame from the video.
        
        Args:
            frame_number: Frame number to retrieve (0-indexed)
        
        Returns:
            Frame as numpy array or None if failed
        """
        if self.cap is None:
            if not self.open():
                return None
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        
        if ret:
            return frame
        return None
    
    def get_middle_frame(self) -> Optional[np.ndarray]:
        """Get the middle frame of the video for calibration preview."""
        metadata = self.get_metadata()
        if metadata is None:
            return None
        
        middle_frame = metadata['frame_count'] // 2
        return self.get_frame(middle_frame)
    
    def iterate_frames(self, start: int = 0, end: Optional[int] = None):
        """
        Generator that yields frames sequentially.
        
        Args:
            start: Starting frame number
            end: Ending frame number (None for all frames)
        """
        if self.cap is None:
            if not self.open():
                return
        
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        
        frame_number = start
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            if end is not None and frame_number >= end:
                break
            
            yield frame_number, frame
            frame_number += 1
    
    def create_video_writer(
        self,
        output_path: str,
        fps: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> Optional[cv2.VideoWriter]:
        """
        Create a video writer for output.
        
        Args:
            output_path: Path for output video
            fps: Output FPS (uses source FPS if None)
            width: Output width (uses source width if None)
            height: Output height (uses source height if None)
        
        Returns:
            VideoWriter object or None if failed
        """
        metadata = self.get_metadata()
        if metadata is None:
            return None
        
        out_width = width if width is not None else metadata['width']
        out_height = height if height is not None else metadata['height']
        out_fps = fps if fps is not None else metadata['fps']
        
        # Use same codec as source or default to MP4V
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        
        writer = cv2.VideoWriter(output_path, fourcc, out_fps, (out_width, out_height))
        
        if not writer.isOpened():
            writer.release()
            return None
        
        return writer
    
    @staticmethod
    def validate_video(path: str) -> Tuple[bool, str]:
        """
        Validate a video file.
        
        Args:
            path: Path to video file
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not Path(path).exists():
            return False, "File does not exist"
        
        supported_extensions = ['.mp4', '.avi', '.mov', '.mkv']
        file_ext = Path(path).suffix.lower()
        
        if file_ext not in supported_extensions:
            return False, f"Unsupported format: {file_ext}"
        
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return False, "Cannot open video file"
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            cap.release()
            return False, "Invalid FPS detected"
        
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if frame_count <= 0:
            cap.release()
            return False, "No frames found in video"
        
        cap.release()
        return True, ""
