import torch
from ultralytics import YOLO
from typing import List, Dict, Any, Optional
import numpy as np


class TrafficCamNet:
    """
    Vehicle detector based on TrafficCamNet architecture.
    Uses YOLOv8 as the underlying detection model for vehicle detection.
    
    Detects relevant traffic classes:
    - car (class 2 in COCO)
    - motorcycle (class 3 in COCO) - used for two-wheeler
    
    This is a modular component that can be replaced with another detector
    without affecting tracking or speed-estimation components.
    """
    
    # Mapping from COCO classes to traffic classes
    CLASS_MAPPING = {
        2: 'car',
        3: 'motorcycle',  # Two-wheeler
    }
    
    # Classes we care about
    TARGET_CLASSES = [2, 3]  # car, motorcycle
    
    def __init__(self, model_path: str = "yolov8n.pt", use_gpu: bool = True):
        """
        Initialize the TrafficCamNet detector.
        
        Args:
            model_path: Path to YOLO model weights
            use_gpu: Whether to use GPU acceleration
        """
        self.model_path = model_path
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.device = 'cuda' if self.use_gpu else 'cpu'
        
        # Load model
        try:
            self.model = YOLO(model_path)
            self.model.to(self.device)
            print(f"TrafficCamNet loaded successfully on {self.device}")
        except Exception as e:
            print(f"Error loading TrafficCamNet model: {e}")
            self.model = None
    
    def detect(self, frame: np.ndarray, confidence_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Detect vehicles in a single frame.
        
        Args:
            frame: Input video frame (BGR format)
            confidence_threshold: Minimum confidence for detections
        
        Returns:
            List of detection dictionaries with keys:
            - bbox: [x1, y1, x2, y2] bounding box
            - class_id: numeric class ID
            - class_name: string class name ('car' or 'two-wheeler')
            - confidence: detection confidence score
            - center: (cx, cy) center of bounding box
            - bottom_center: (x, bottom_y) bottom-center point for ground contact
        """
        if self.model is None:
            return []
        
        detections = []
        
        try:
            # Run inference
            results = self.model(
                frame,
                conf=confidence_threshold,
                classes=self.TARGET_CLASSES,
                verbose=False
            )
            
            # Process results
            if len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                
                for i in range(len(boxes)):
                    # Get bounding box
                    bbox = boxes.xyxy[i].cpu().numpy()
                    x1, y1, x2, y2 = bbox
                    
                    # Get class and confidence
                    class_id = int(boxes.cls[i].cpu().numpy())
                    confidence = float(boxes.conf[i].cpu().numpy())
                    
                    # Map to traffic class name
                    class_name = self.CLASS_MAPPING.get(class_id, 'unknown')
                    if class_id == 3:
                        class_name = 'two-wheeler'
                    
                    # Calculate center and bottom-center
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    bottom_center_x = cx
                    bottom_center_y = y2  # Bottom of bounding box
                    
                    detections.append({
                        'bbox': [float(x1), float(y1), float(x2), float(y2)],
                        'class_id': class_id,
                        'class_name': class_name,
                        'confidence': confidence,
                        'center': (float(cx), float(cy)),
                        'bottom_center': (float(bottom_center_x), float(bottom_center_y))
                    })
        
        except Exception as e:
            print(f"Error during detection: {e}")
        
        return detections
    
    def detect_batch(self, frames: List[np.ndarray], confidence_threshold: float = 0.5) -> List[List[Dict[str, Any]]]:
        """
        Detect vehicles in a batch of frames.
        
        Args:
            frames: List of input video frames
            confidence_threshold: Minimum confidence for detections
        
        Returns:
            List of detection lists (one per frame)
        """
        if self.model is None or len(frames) == 0:
            return [[] for _ in frames]
        
        all_detections = []
        
        try:
            # Run batch inference
            results = self.model(
                frames,
                conf=confidence_threshold,
                classes=self.TARGET_CLASSES,
                verbose=False
            )
            
            # Process each frame's results
            for result in results:
                frame_detections = []
                
                if result.boxes is not None:
                    boxes = result.boxes
                    
                    for i in range(len(boxes)):
                        bbox = boxes.xyxy[i].cpu().numpy()
                        x1, y1, x2, y2 = bbox
                        
                        class_id = int(boxes.cls[i].cpu().numpy())
                        confidence = float(boxes.conf[i].cpu().numpy())
                        
                        class_name = self.CLASS_MAPPING.get(class_id, 'unknown')
                        if class_id == 3:
                            class_name = 'two-wheeler'
                        
                        cx = (x1 + x2) / 2
                        cy = (y1 + y2) / 2
                        
                        frame_detections.append({
                            'bbox': [float(x1), float(y1), float(x2), float(y2)],
                            'class_id': class_id,
                            'class_name': class_name,
                            'confidence': confidence,
                            'center': (float(cx), float(cy)),
                            'bottom_center': (float(cx), float(y2))
                        })
                
                all_detections.append(frame_detections)
        
        except Exception as e:
            print(f"Error during batch detection: {e}")
            all_detections = [[] for _ in frames]
        
        return all_detections
    
    def get_model_info(self) -> Dict[str, Any]:
        """Return information about the loaded model."""
        return {
            'model_path': self.model_path,
            'device': self.device,
            'use_gpu': self.use_gpu,
            'target_classes': self.TARGET_CLASSES,
            'class_mapping': self.CLASS_MAPPING
        }
