export interface Video {
  id: number;
  filename: string;
  resolution_width: number;
  resolution_height: number;
  fps: number;
  duration: number;
  frame_count: number;
  processing_status: string;
  uploaded_at: string;
  has_calibration: boolean;
  processed_video_path?: string;
}

export interface Calibration {
  id: number;
  video_id: number;
  image_points: number[][];
  real_world_points: number[][];
  homography_matrix?: number[][];
  created_at: string;
  is_validated: boolean;
}

export interface ProcessingJob {
  id: number;
  video_id: number;
  status: string;
  progress_percentage: number;
  current_frame: number;
  total_frames: number;
  vehicles_detected: number;
  vehicles_tracked: number;
  processing_fps?: number;
  elapsed_time?: number;
  estimated_remaining_time?: number;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
}

export interface TrajectoryPoint {
  frame_number: number;
  timestamp: number;
  image_x: number;
  image_y: number;
  world_x?: number;
  world_y?: number;
  speed_kmh?: number;
  smoothed_speed_kmh?: number;
}

export interface VehicleTrack {
  id: number;
  track_id: number;
  vehicle_type: string;
  start_time: number;
  end_time: number;
  duration_seconds: number;
  distance_meters: number;
  average_speed_kmh: number;
  maximum_speed_kmh: number;
  minimum_speed_kmh: number;
  confidence: number;
  overspeed: boolean;
  trajectory_points?: TrajectoryPoint[];
}

export interface VideoResults {
  video_id: number;
  total_vehicles: number;
  average_speed: number;
  maximum_speed: number;
  overspeed_count: number;
  tracks: VehicleTrack[];
}

export interface DashboardStats {
  total_videos_processed: number;
  total_vehicles_detected: number;
  average_vehicle_speed: number;
  maximum_detected_speed: number;
  overspeed_vehicles_count: number;
  recent_jobs: ProcessingJob[];
}

export interface ValidationMetrics {
  mae: number;
  mape: number;
  rmse: number;
  mean_error: number;
  std_error: number;
  sample_count: number;
}
