import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { Image as ImageIcon, Video, Camera, AlertTriangle, RefreshCw, Loader2 } from 'lucide-react';

const API = 'http://localhost:8000/api';

interface Stats {
  total_sessions:   number;
  image_sessions:   number;
  video_sessions:   number;
  webcam_sessions:  number;
  failed_sessions:  number;
  total_detections: number;
  top_classes:      { class: string; count: number }[];
  top_ppe_classes?: { class: string; count: number }[];
  daily_sessions:   { date: string; count: number }[];
  model_note:       string;
}

const StatCard: React.FC<{ label: string; value: number | string; icon: React.ReactNode; color: string }> = ({ label, value, icon, color }) => (
  <div className="bg-white rounded-lg border border-gray-200 p-5 flex items-center gap-4 shadow-sm">
    <div className={`p-3 rounded-lg ${color}`}>{icon}</div>
    <div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  </div>
);

const Dashboard: React.FC = () => {
  const [stats, setStats]     = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<Stats>(`${API}/dashboard/stats`);
      setStats(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Failed to load statistics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center justify-center h-64 gap-4">
      <AlertTriangle className="w-10 h-10 text-red-400" />
      <p className="text-red-600 text-sm">{error}</p>
      <button onClick={load} className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700">
        <RefreshCw className="w-4 h-4" /> Retry
      </button>
    </div>
  );

  if (!stats || stats.total_sessions === 0) return (
    <div className="bg-white rounded-lg border border-gray-200 p-12 flex flex-col items-center gap-3 shadow-sm">
      <BarChart className="w-12 h-12 text-gray-300" />
      <p className="text-gray-500 text-sm">No detection sessions yet. Run image, video, or webcam detection to see statistics here.</p>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard label="Total Sessions"    value={stats.total_sessions}   icon={<BarChart className="w-5 h-5 text-blue-600" />}   color="bg-blue-50" />
        <StatCard label="Total Detections"  value={stats.total_detections} icon={<AlertTriangle className="w-5 h-5 text-yellow-600" />} color="bg-yellow-50" />
        <StatCard label="Image Sessions"    value={stats.image_sessions}   icon={<ImageIcon className="w-5 h-5 text-green-600" />}  color="bg-green-50" />
        <StatCard label="Video Sessions"    value={stats.video_sessions}   icon={<Video className="w-5 h-5 text-purple-600" />}    color="bg-purple-50" />
        <StatCard label="Webcam Sessions"   value={stats.webcam_sessions}  icon={<Camera className="w-5 h-5 text-cyan-600" />}     color="bg-cyan-50" />
        <StatCard label="Failed Sessions"   value={stats.failed_sessions}  icon={<AlertTriangle className="w-5 h-5 text-red-600" />}  color="bg-red-50" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Daily sessions */}
        {stats.daily_sessions.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Sessions (7 Days)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={stats.daily_sessions}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Top PPE classes */}
        {stats.top_ppe_classes && stats.top_ppe_classes.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Top PPE Detections</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={stats.top_ppe_classes} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="class" width={80} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#14b8a6" radius={[0,4,4,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Refresh button */}
      <div className="flex justify-end">
        <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>
    </div>
  );
};

export default Dashboard;
