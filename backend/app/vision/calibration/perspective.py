import cv2
import numpy as np
from typing import List, Tuple, Optional


class PerspectiveCalibration:
    """
    Handles perspective transformation and homography calculation
    for converting image coordinates to real-world ground-plane coordinates.
    """
    
    def __init__(self):
        self.homography_matrix: Optional[np.ndarray] = None
        self.image_points: List[Tuple[float, float]] = []
        self.real_world_points: List[Tuple[float, float]] = []
    
    def set_calibration_points(
        self,
        image_points: List[List[float]],
        real_world_points: List[List[float]]
    ) -> bool:
        """
        Set calibration points and compute homography matrix.
        
        Args:
            image_points: List of [x, y] coordinates in image space
            real_world_points: List of [x, y] coordinates in real-world meters
        
        Returns:
            True if homography was successfully computed
        """
        if len(image_points) < 4 or len(real_world_points) < 4:
            return False
        
        if len(image_points) != len(real_world_points):
            return False
        
        self.image_points = [(p[0], p[1]) for p in image_points]
        self.real_world_points = [(p[0], p[1]) for p in real_world_points]
        
        # Convert to numpy arrays
        src_points = np.array(self.image_points, dtype=np.float32)
        dst_points = np.array(self.real_world_points, dtype=np.float32)
        
        # Compute homography matrix
        try:
            self.homography_matrix, _ = cv2.findHomography(src_points, dst_points)
            return True
        except Exception as e:
            print(f"Error computing homography: {e}")
            return False
    
    def image_to_world(self, image_x: float, image_y: float) -> Optional[Tuple[float, float]]:
        """
        Transform image coordinates to real-world coordinates.
        
        Args:
            image_x: X coordinate in image space (pixels)
            image_y: Y coordinate in image space (pixels)
        
        Returns:
            Tuple of (world_x, world_y) in meters, or None if transformation fails
        """
        if self.homography_matrix is None:
            return None
        
        point = np.array([[image_x, image_y]], dtype=np.float32)
        point = point.reshape(-1, 1, 2)
        
        try:
            world_point = cv2.perspectiveTransform(point, self.homography_matrix)
            return (float(world_point[0][0][0]), float(world_point[0][0][1]))
        except Exception as e:
            print(f"Error transforming point: {e}")
            return None
    
    def world_to_image(self, world_x: float, world_y: float) -> Optional[Tuple[float, float]]:
        """
        Transform real-world coordinates to image coordinates.
        
        Args:
            world_x: X coordinate in real-world space (meters)
            world_y: Y coordinate in real-world space (meters)
        
        Returns:
            Tuple of (image_x, image_y) in pixels, or None if transformation fails
        """
        if self.homography_matrix is None:
            return None
        
        # Compute inverse homography
        try:
            inv_homography = np.linalg.inv(self.homography_matrix)
            point = np.array([[world_x, world_y]], dtype=np.float32)
            point = point.reshape(-1, 1, 2)
            
            image_point = cv2.perspectiveTransform(point, inv_homography)
            return (float(image_point[0][0][0]), float(image_point[0][0][1]))
        except Exception as e:
            print(f"Error transforming point: {e}")
            return None
    
    def get_homography_matrix(self) -> Optional[List[List[float]]]:
        """Return homography matrix as nested list for JSON serialization."""
        if self.homography_matrix is None:
            return None
        return self.homography_matrix.tolist()
    
    def validate_calibration(self, test_points: List[Tuple[float, float, float, float]]) -> float:
        """
        Validate calibration accuracy using test points.
        
        Args:
            test_points: List of (image_x, image_y, expected_world_x, expected_world_y)
        
        Returns:
            Mean error in meters
        """
        if not test_points or self.homography_matrix is None:
            return float('inf')
        
        errors = []
        for img_x, img_y, exp_world_x, exp_world_y in test_points:
            result = self.image_to_world(img_x, img_y)
            if result:
                world_x, world_y = result
                error = np.sqrt((world_x - exp_world_x)**2 + **(world_y - exp_world_y)2)
                errors.append(error)
        
        return np.mean(errors) if errors else float('inf')
    
    def generate_birds_eye_view(self, frame: np.ndarray, output_size: Tuple[int, int]) -> np.ndarray:
        """
        Generate a bird's-eye view of the frame using the homography.
        
        Args:
            frame: Input video frame
            output_size: (width, height) of output image
        
        Returns:
            Bird's-eye view image
        """
        if self.homography_matrix is None:
            return frame
        
        try:
            warped = cv2.warpPerspective(frame, self.homography_matrix, output_size)
            return warped
        except Exception as e:
            print(f"Error generating bird's eye view: {e}")
            return frame
    
    def draw_calibration_overlay(
        self,
        frame: np.ndarray,
        show_grid: bool = True,
        grid_spacing: float = 1.0
    ) -> np.ndarray:
        """
        Draw calibration overlay on frame showing road plane and grid.
        
        Args:
            frame: Input video frame
            show_grid: Whether to show coordinate grid
            grid_spacing: Spacing of grid lines in meters
        
        Returns:
            Frame with overlay
        """
        overlay = frame.copy()
        
        # Draw calibration polygon
        if len(self.image_points) >= 4:
            pts = np.array(self.image_points, dtype=np.int32)
            pts = pts.reshape((-1, 1, 2))
            cv2.polylines(overlay, [pts], True, (0, 255, 0), 2)
            
            # Draw point labels
            for i, pt in enumerate(self.image_points):
                label = f"P{i+1}"
                cv2.putText(overlay, label, (int(pt[0]) + 5, int(pt[1]) - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw grid lines in world coordinates transformed to image
        if show_grid and self.homography_matrix is not None:
            try:
                inv_h = np.linalg.inv(self.homography_matrix)
                
                # Determine bounds from real-world points
                world_pts = np.array(self.real_world_points)
                min_x, min_y = np.min(world_pts, axis=0)
                max_x, max_y = np.max(world_pts, axis=0)
                
                # Draw vertical grid lines
                x = min_x
                while x <= max_x:
                    # Create line in world coordinates
                    world_line = np.array([
                        [[x, min_y]],
                        [[x, max_y]]
                    ], dtype=np.float32)
                    
                    # Transform to image coordinates
                    image_line = cv2.perspectiveTransform(world_line, inv_h)
                    pt1 = tuple(map(int, image_line[0][0]))
                    pt2 = tuple(map(int, image_line[1][0]))
                    
                    cv2.line(overlay, pt1, pt2, (255, 0, 0), 1)
                    x += grid_spacing
                
                # Draw horizontal grid lines
                y = min_y
                while y <= max_y:
                    world_line = np.array([
                        [[min_x, y]],
                        [[max_x, y]]
                    ], dtype=np.float32)
                    
                    image_line = cv2.perspectiveTransform(world_line, inv_h)
                    pt1 = tuple(map(int, image_line[0][0]))
                    pt2 = tuple(map(int, image_line[1][0]))
                    
                    cv2.line(overlay, pt1, pt2, (255, 0, 0), 1)
                    y += grid_spacing
                    
            except Exception as e:
                print(f"Error drawing grid: {e}")
        
        return overlay
