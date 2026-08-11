import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { processingApi } from '../services/api';
import { PlayCircle, Loader2 } from 'lucide-react';

export default function Processing() {
  const { videoId } = useParams<{ videoId: string }>();
  const navigate = useNavigate();
  
  const [job, setJob] = useState<any>(null);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    if (videoId) {
      startProcessing();
    }
  }, [videoId]);

  useEffect(() => {
    if (job?.status === 'running') {
      const interval = setInterval(pollStatus, 2000);
      return () => clearInterval(interval);
    } else if (job?.status === 'completed') {
      setTimeout(() => navigate(`/results/${videoId}`), 2000);
    }
  }, [job?.status]);

  async function startProcessing() {
    try {
      const result = await processingApi.start({
        video_id: Number(videoId),
        speed_limit: 60,
        smoothing_window: 5
      });
      setJob({ id: result.job_id, status: 'pending' });
      pollStatus();
    } catch (error) {
      console.error('Failed to start processing:', error);
    }
  }

  async function pollStatus() {
    if (!job?.id) return;
    
    try {
      const status = await processingApi.getStatus(job.id);
      setJob(status);
      setProcessing(status.status === 'running' || status.status === 'pending');
    } catch (error) {
      console.error('Failed to get status:', error);
    }
  }

  function formatTime(seconds?: number) {
    if (!seconds) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Processing Video</h2>

      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="flex items-center mb-4">
          {processing ? (
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin mr-3" />
          ) : (
            <PlayCircle className="w-8 h-8 text-green-600 mr-3" />
          )}
          <div>
            <h3 className="font-semibold text-lg">
              {job?.status === 'completed' ? 'Processing Complete' : 
               job?.status === 'failed' ? 'Processing Failed' : 'Processing...'}
            </h3>
            <p className="text-sm text-gray-500">Video #{videoId}</p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mb-6">
          <div className="flex justify-between text-sm mb-2">
            <span>Progress</span>
            <span>{job?.progress_percentage?.toFixed(1) || 0}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className={`h-3 rounded-full transition-all ${
                job?.status === 'failed' ? 'bg-red-600' : 'bg-blue-600'
              }`}
              style={{ width: `${job?.progress_percentage || 0}%` }}
            />
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-gray-50 p-3 rounded">
            <p className="text-xs text-gray-500">Frame</p>
            <p className="font-semibold">{job?.current_frame || 0} / {job?.total_frames || 0}</p>
          </div>
          <div className="bg-gray-50 p-3 rounded">
            <p className="text-xs text-gray-500">Vehicles</p>
            <p className="font-semibold">{job?.vehicles_tracked || 0}</p>
          </div>
          <div className="bg-gray-50 p-3 rounded">
            <p className="text-xs text-gray-500">Speed</p>
            <p className="font-semibold">{job?.processing_fps?.toFixed(1) || 0} FPS</p>
          </div>
          <div className="bg-gray-50 p-3 rounded">
            <p className="text-xs text-gray-500">Elapsed</p>
            <p className="font-semibold">{formatTime(job?.elapsed_time)}</p>
          </div>
        </div>

        {/* ETA */}
        {job?.estimated_remaining_time !== undefined && job.status === 'running' && (
          <div className="bg-blue-50 border border-blue-200 rounded p-3">
            <p className="text-sm text-blue-800">
              Estimated time remaining: {formatTime(job.estimated_remaining_time)}
            </p>
          </div>
        )}

        {/* Error Message */}
        {job?.status === 'failed' && job?.error_message && (
          <div className="bg-red-50 border border-red-200 rounded p-4">
            <p className="text-red-800 font-medium">Error</p>
            <p className="text-sm text-red-700 mt-1">{job.error_message}</p>
          </div>
        )}

        {/* Actions */}
        {job?.status === 'completed' && (
          <button
            onClick={() => navigate(`/results/${videoId}`)}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            View Results
          </button>
        )}

        {job?.status === 'failed' && (
          <button
            onClick={() => navigate('/upload')}
            className="w-full px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            Upload Another Video
          </button>
        )}
      </div>
    </div>
  );
}
