import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const videoApi = {
  upload: async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  getVideos: async (): Promise<any[]> => {
    const response = await api.get('/videos');
    return response.data;
  },

  getVideo: async (id: number): Promise<any> => {
    const response = await api.get(`/videos/${id}`);
    return response.data;
  },

  deleteVideo: async (id: number): Promise<void> => {
    await api.delete(`/videos/${id}`);
  },

  getFrame: async (videoId: number): Promise<Blob> => {
    const response = await api.get(`/videos/${videoId}/frame`, {
      responseType: 'blob',
    });
    return response.data;
  },
};

export const calibrationApi = {
  save: async (data: {
    video_id: number;
    image_points: number[][];
    real_world_points: number[][];
  }): Promise<any> => {
    const response = await api.post('/calibration', data);
    return response.data;
  },

  get: async (videoId: number): Promise<any | null> => {
    const response = await api.get(`/calibration/${videoId}`);
    return response.data;
  },

  validate: async (videoId: number): Promise<any> => {
    const response = await api.post(`/calibration/${videoId}/validate`);
    return response.data;
  },
};

export const processingApi = {
  start: async (data: {
    video_id: number;
    speed_limit?: number;
    smoothing_window?: number;
  }): Promise<any> => {
    const response = await api.post('/process', data);
    return response.data;
  },

  getStatus: async (jobId: number): Promise<any> => {
    const response = await api.get(`/jobs/${jobId}`);
    return response.data;
  },
};

export const resultsApi = {
  getResults: async (videoId: number): Promise<any> => {
    const response = await api.get(`/results/${videoId}`);
    return response.data;
  },

  downloadVideo: async (videoId: number): Promise<void> => {
    const response = await api.get(`/download/video/${videoId}`, {
      responseType: 'blob',
    });
    
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `processed_video_${videoId}.mp4`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },

  downloadCSV: async (videoId: number): Promise<void> => {
    const response = await api.get(`/download/csv/${videoId}`);
    
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `results_${videoId}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  },
};

export const validationApi = {
  addValidation: async (data: {
    video_id: number;
    track_id: number;
    reference_speed_kmh: number;
    estimated_speed_kmh: number;
  }): Promise<any> => {
    const response = await api.post('/validation', data);
    return response.data;
  },

  getMetrics: async (videoId: number): Promise<any | null> => {
    const response = await api.get(`/validation/${videoId}/metrics`);
    return response.data;
  },
};

export const dashboardApi = {
  getStats: async (): Promise<any> => {
    const response = await api.get('/dashboard');
    return response.data;
  },
};

export default api;
