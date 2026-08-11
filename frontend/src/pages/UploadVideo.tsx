import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { videoApi } from '../services/api';
import { Upload as UploadIcon, FileVideo } from 'lucide-react';

export default function UploadVideo() {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const navigate = useNavigate();

  async function handleFileSelect(file: File) {
    if (!file) return;

    const validTypes = ['.mp4', '.avi', '.mov', '.mkv'];
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!validTypes.includes(ext)) {
      alert('Invalid file format. Supported: MP4, AVI, MOV, MKV');
      return;
    }

    setUploading(true);
    setProgress(0);

    try {
      const result = await videoApi.upload(file);
      setProgress(100);
      setTimeout(() => {
        navigate(`/calibration/${result.id}`);
      }, 500);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Upload Video</h2>
      
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-blue-500 transition-colors"
      >
        <UploadIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <p className="text-lg text-gray-600 mb-2">Drag and drop your video here</p>
        <p className="text-sm text-gray-500 mb-4">or click to browse</p>
        <label className="inline-block">
          <input
            type="file"
            accept=".mp4,.avi,.mov,.mkv"
            onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
            className="hidden"
          />
          <span className="px-4 py-2 bg-blue-600 text-white rounded-md cursor-pointer hover:bg-blue-700">
            Browse Files
          </span>
        </label>
        <p className="text-xs text-gray-400 mt-4">Supported formats: MP4, AVI, MOV, MKV (Max 500MB)</p>
      </div>

      {uploading && (
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center mb-2">
            <FileVideo className="w-5 h-5 text-blue-600 mr-2" />
            <span className="font-medium">Uploading...</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="text-sm text-gray-500 mt-2">{progress}% complete</p>
        </div>
      )}
    </div>
  );
}
