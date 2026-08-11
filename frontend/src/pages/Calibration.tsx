import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { videoApi, calibrationApi } from '../services/api';
import { Save, Check, AlertCircle } from 'lucide-react';

export default function Calibration() {
  const { videoId } = useParams<{ videoId: string }>();
  const navigate = useNavigate();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  const [video, setVideo] = useState<any>(null);
  const [imagePoints, setImagePoints] = useState<number[][]>([]);
  const [realWorldPoints, setRealWorldPoints] = useState<number[][]>([
    [0, 0], [10, 0], [10, 5], [0, 5]
  ]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (videoId) {
      loadVideoInfo();
    }
  }, [videoId]);

  async function loadVideoInfo() {
    try {
      const data = await videoApi.getVideo(Number(videoId));
      setVideo(data);
      
      // Load existing calibration if available
      if (data.has_calibration) {
        const cal = await calibrationApi.get(Number(videoId));
        if (cal) {
          setImagePoints(cal.image_points);
          setRealWorldPoints(cal.real_world_points);
        }
      }
    } catch (error) {
      console.error('Failed to load video:', error);
    }
  }

  function handleCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    if (imagePoints.length >= 4) return;
    
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    setImagePoints([...imagePoints, [x, y]]);
  }

  function updateRealWorldPoint(index: number, value: number, coord: 'x' | 'y') {
    const newPoints = [...realWorldPoints];
    if (coord === 'x') {
      newPoints[index][0] = parseFloat(value.toString()) || 0;
    } else {
      newPoints[index][1] = parseFloat(value.toString()) || 0;
    }
    setRealWorldPoints(newPoints);
  }

  async function handleSave() {
    if (imagePoints.length < 4) {
      alert('Please select at least 4 calibration points');
      return;
    }

    setSaving(true);
    try {
      await calibrationApi.save({
        video_id: Number(videoId),
        image_points: imagePoints,
        real_world_points: realWorldPoints
      });
      await calibrationApi.validate(Number(videoId));
      navigate(`/processing/${videoId}`);
    } catch (error) {
      console.error('Save failed:', error);
      alert('Failed to save calibration');
    } finally {
      setSaving(false);
    }
  }

  function resetPoints() {
    setImagePoints([]);
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Road Calibration</h2>
        <button
          onClick={resetPoints}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900"
        >
          Reset Points
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Canvas */}
        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg shadow-sm border p-4">
            <p className="text-sm text-gray-600 mb-4">
              Click on 4 points on the road surface to define the measurement area.
              Start from top-left and go clockwise.
            </p>
            <div className="relative">
              <canvas
                ref={canvasRef}
                onClick={handleCanvasClick}
                className="w-full border rounded cursor-crosshair"
                width={video?.resolution_width || 640}
                height={video?.resolution_height || 480}
              />
              {imagePoints.map((point, index) => (
                <div
                  key={index}
                  className="absolute w-4 h-4 bg-red-500 rounded-full transform -translate-x-1/2 -translate-y-1/2"
                  style={{ left: point[0], top: point[1] }}
                />
              ))}
            </div>
            <p className="text-sm text-gray-500 mt-2">
              Points selected: {imagePoints.length}/4
            </p>
          </div>
        </div>

        {/* Real-world coordinates */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg shadow-sm border p-4">
            <h3 className="font-semibold mb-4">Real-World Coordinates (meters)</h3>
            {realWorldPoints.map((point, index) => (
              <div key={index} className="flex items-center gap-2 mb-3">
                <span className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-sm font-medium">
                  {index + 1}
                </span>
                <div className="flex-1 grid grid-cols-2 gap-2">
                  <input
                    type="number"
                    value={point[0]}
                    onChange={(e) => updateRealWorldPoint(index, parseFloat(e.target.value), 'x')}
                    className="border rounded px-2 py-1 text-sm"
                    placeholder="X (m)"
                  />
                  <input
                    type="number"
                    value={point[1]}
                    onChange={(e) => updateRealWorldPoint(index, parseFloat(e.target.value), 'y')}
                    className="border rounded px-2 py-1 text-sm"
                    placeholder="Y (m)"
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-start">
              <AlertCircle className="w-5 h-5 text-yellow-600 mr-2 flex-shrink-0" />
              <div>
                <h4 className="font-medium text-yellow-800">Accuracy Note</h4>
                <p className="text-sm text-yellow-700 mt-1">
                  For accurate speed estimation, measure the real-world distances carefully. 
                  The system uses perspective transformation to convert pixel positions to meters.
                </p>
              </div>
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={imagePoints.length < 4 || saving}
            className="w-full flex items-center justify-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : (
              <>
                <Save className="w-4 h-4 mr-2" />
                Save & Continue
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
