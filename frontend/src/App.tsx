import { useState } from 'react';
import { Camera, Video, Image as ImageIcon, LayoutDashboard, History as LucideHistory, Settings } from 'lucide-react';
import ImageDetection from './features/ImageDetection';
import VideoDetection from './features/VideoDetection';
import WebcamMonitor  from './features/WebcamMonitor';
import Dashboard      from './features/Dashboard';
import HistoryPage    from './features/History';

function App() {
  const [activeTab, setActiveTab] = useState('image');

  const renderContent = () => {
    switch (activeTab) {
      case 'image':     return <ImageDetection />;
      case 'video':     return <VideoDetection />;
      case 'webcam':    return <WebcamMonitor />;
      case 'dashboard': return <Dashboard />;
      case 'history':   return <HistoryPage />;
      default:
        return (
          <div className="bg-white border border-gray-200 rounded-lg h-96 flex items-center justify-center">
            <p className="text-gray-500">Content for {activeTab} will go here.</p>
          </div>
        );
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200">
        <div className="p-6">
          <h1 className="text-xl font-bold text-gray-800">SafeVision AI</h1>
          <p className="text-sm text-gray-500">Hackathon Project</p>
        </div>
        <nav className="mt-6">
          <div className="px-4 pb-4 space-y-1">
            <button onClick={() => setActiveTab('image')} className={`flex items-center w-full px-4 py-2 text-sm font-medium rounded-md ${activeTab === 'image' ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}>
              <ImageIcon className="w-5 h-5 mr-3" />
              Image Detection
            </button>
            <button onClick={() => setActiveTab('video')} className={`flex items-center w-full px-4 py-2 text-sm font-medium rounded-md ${activeTab === 'video' ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}>
              <Video className="w-5 h-5 mr-3" />
              Video Detection
            </button>
            <button onClick={() => setActiveTab('webcam')} className={`flex items-center w-full px-4 py-2 text-sm font-medium rounded-md ${activeTab === 'webcam' ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}>
              <Camera className="w-5 h-5 mr-3" />
              Webcam Feed
            </button>
            <button onClick={() => setActiveTab('dashboard')} className={`flex items-center w-full px-4 py-2 text-sm font-medium rounded-md ${activeTab === 'dashboard' ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}>
              <LayoutDashboard className="w-5 h-5 mr-3" />
              Dashboard
            </button>
            <button onClick={() => setActiveTab('history')} className={`flex items-center w-full px-4 py-2 text-sm font-medium rounded-md ${activeTab === 'history' ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-50'}`}>
              <LucideHistory className="w-5 h-5 mr-3" />
              History
            </button>
          </div>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <header className="bg-white shadow-sm">
          <div className="px-8 py-4 flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-800 capitalize">
              {activeTab} Module
            </h2>
            <button className="p-2 text-gray-400 hover:text-gray-500">
              <Settings className="w-6 h-6" />
            </button>
          </div>
        </header>

        <div className="p-8">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}

export default App;
