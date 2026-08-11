import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { resultsApi } from '../services/api';
import type { VideoResults } from '../types';
import { Download, FileDown } from 'lucide-react';

export default function Results() {
  const { videoId } = useParams<{ videoId: string }>();
  const [results, setResults] = useState<VideoResults | null>(null);
  const [filter, setFilter] = useState<'all' | 'overspeed'>('all');
  const [sortBy, setSortBy] = useState<'id' | 'speed'>('id');

  useEffect(() => {
    if (videoId) {
      loadResults();
    }
  }, [videoId]);

  async function loadResults() {
    try {
      const data = await resultsApi.getResults(Number(videoId));
      setResults(data);
    } catch (error) {
      console.error('Failed to load results:', error);
    }
  }

  function getFilteredTracks() {
    if (!results) return [];
    
    let tracks = [...results.tracks];
    
    if (filter === 'overspeed') {
      tracks = tracks.filter(t => t.overspeed);
    }
    
    if (sortBy === 'speed') {
      tracks.sort((a, b) => b.average_speed_kmh - a.average_speed_kmh);
    } else {
      tracks.sort((a, b) => a.track_id - b.track_id);
    }
    
    return tracks;
  }

  function getSpeedColor(speed: number, limit = 60) {
    if (speed > limit) return 'text-red-600 font-semibold';
    if (speed > limit * 0.8) return 'text-yellow-600';
    return 'text-green-600';
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Analysis Results</h2>
        <div className="flex gap-2">
          <button
            onClick={() => resultsApi.downloadVideo(Number(videoId))}
            className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            <Download className="w-4 h-4 mr-2" />
            Download Video
          </button>
          <button
            onClick={() => resultsApi.downloadCSV(Number(videoId))}
            className="flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
          >
            <FileDown className="w-4 h-4 mr-2" />
            Download CSV
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      {results && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-lg shadow-sm border">
            <p className="text-sm text-gray-500">Total Vehicles</p>
            <p className="text-2xl font-bold">{results.total_vehicles}</p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border">
            <p className="text-sm text-gray-500">Average Speed</p>
            <p className="text-2xl font-bold">{results.average_speed} km/h</p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border">
            <p className="text-sm text-gray-500">Maximum Speed</p>
            <p className="text-2xl font-bold">{results.maximum_speed} km/h</p>
          </div>
          <div className="bg-white p-4 rounded-lg shadow-sm border">
            <p className="text-sm text-gray-500">Overspeed Count</p>
            <p className="text-2xl font-bold text-red-600">{results.overspeed_count}</p>
          </div>
        </div>
      )}

      {/* Results Table */}
      <div className="bg-white rounded-lg shadow-sm border">
        <div className="px-6 py-4 border-b flex justify-between items-center">
          <h3 className="font-semibold">Vehicle Tracks</h3>
          <div className="flex gap-2">
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value as 'all' | 'overspeed')}
              className="border rounded px-2 py-1 text-sm"
            >
              <option value="all">All Vehicles</option>
              <option value="overspeed">Overspeed Only</option>
            </select>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'id' | 'speed')}
              className="border rounded px-2 py-1 text-sm"
            >
              <option value="id">Sort by ID</option>
              <option value="speed">Sort by Speed</option>
            </select>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Avg Speed</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Max Speed</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Distance</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Duration</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {getFilteredTracks().map((track) => (
                <tr key={track.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">#{track.track_id}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm capitalize">{track.vehicle_type}</td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm ${getSpeedColor(track.average_speed_kmh)}`}>
                    {track.average_speed_kmh.toFixed(1)} km/h
                  </td>
                  <td className={`px-6 py-4 whitespace-nowrap text-sm ${getSpeedColor(track.maximum_speed_kmh)}`}>
                    {track.maximum_speed_kmh.toFixed(1)} km/h
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{track.distance_meters.toFixed(1)} m</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">{track.duration_seconds.toFixed(1)} s</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {track.overspeed ? (
                      <span className="px-2 py-1 text-xs rounded-full bg-red-100 text-red-800">Overspeed</span>
                    ) : (
                      <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">Normal</span>
                    )}
                  </td>
                </tr>
              ))}
              {getFilteredTracks().length === 0 && (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                    No vehicles found matching the filter criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-600">
          <strong>Note:</strong> Speed estimates are based on perspective transformation and may have 
          measurement errors. For research purposes only. Actual vehicle speeds may vary.
        </p>
      </div>
    </div>
  );
}
