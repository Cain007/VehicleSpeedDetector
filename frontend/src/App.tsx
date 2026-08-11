import { Routes, Route, Link } from 'react-router-dom';
import { LayoutDashboard, Upload, Ruler, PlayCircle, BarChart3 } from 'lucide-react';

// Pages
import Dashboard from './pages/Dashboard';
import UploadVideo from './pages/UploadVideo';
import Calibration from './pages/Calibration';
import Processing from './pages/Processing';
import Results from './pages/Results';

function App() {
  return (
    <div className="min-h-screen bg-gray-100">
      {/* Navigation */}
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold text-gray-900">CCTV Speed Detection</h1>
            </div>
            <div className="flex items-center space-x-4">
              <Link to="/" className="flex items-center px-3 py-2 text-sm text-gray-700 hover:text-blue-600">
                <LayoutDashboard className="w-4 h-4 mr-2" />
                Dashboard
              </Link>
              <Link to="/upload" className="flex items-center px-3 py-2 text-sm text-gray-700 hover:text-blue-600">
                <Upload className="w-4 h-4 mr-2" />
                Upload
              </Link>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<UploadVideo />} />
          <Route path="/calibration/:videoId" element={<Calibration />} />
          <Route path="/processing/:videoId" element={<Processing />} />
          <Route path="/results/:videoId" element={<Results />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
