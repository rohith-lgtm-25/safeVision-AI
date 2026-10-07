import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { Loader2, AlertTriangle, RefreshCw, Image as ImageIcon, Video, Camera, ChevronLeft, ChevronRight } from 'lucide-react';

const API = 'http://localhost:8000/api';
const PAGE_SIZE = 20;

interface Session {
  id:               number;
  source_type:      'image' | 'video' | 'webcam';
  created_at:       string;
  status:           string;
  filename:         string | null;
  duration_seconds: number | null;
  total_detections: number;
  class_counts:     Record<string, number>;
  ppe_counts:       Record<string, number> | null;
  error_message:    string | null;
}

interface HistoryResponse {
  total:   number;
  limit:   number;
  offset:  number;
  results: Session[];
}

const SOURCE_ICON: Record<string, React.ReactNode> = {
  image:  <ImageIcon className="w-4 h-4 text-green-600" />,
  video:  <Video className="w-4 h-4 text-purple-600" />,
  webcam: <Camera className="w-4 h-4 text-cyan-600" />,
};

const STATUS_BADGE: Record<string, string> = {
  completed:  'bg-green-100 text-green-700',
  failed:     'bg-red-100 text-red-700',
  processing: 'bg-yellow-100 text-yellow-700',
};

function formatDate(iso: string): string {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

const History: React.FC = () => {
  const [data,       setData]       = useState<HistoryResponse | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page,       setPage]       = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = {
        limit:  PAGE_SIZE,
        offset: page * PAGE_SIZE,
      };
      if (sourceFilter) params.source_type = sourceFilter;
      if (statusFilter) params.status      = statusFilter;
      const res = await axios.get<HistoryResponse>(`${API}/history`, { params });
      setData(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Failed to load history.');
    } finally {
      setLoading(false);
    }
  }, [sourceFilter, statusFilter, page]);

  useEffect(() => { load(); }, [load]);

  // Reset to page 0 when filters change
  const handleFilter = (setter: React.Dispatch<React.SetStateAction<string>>, value: string) => {
    setter(value);
    setPage(0);
  };

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm flex flex-wrap gap-4 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Source</label>
          <select
            value={sourceFilter}
            onChange={e => handleFilter(setSourceFilter, e.target.value)}
            className="px-3 py-1.5 border border-gray-300 rounded text-sm"
          >
            <option value="">All</option>
            <option value="image">Image</option>
            <option value="video">Video</option>
            <option value="webcam">Webcam</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={e => handleFilter(setStatusFilter, e.target.value)}
            className="px-3 py-1.5 border border-gray-300 rounded text-sm"
          >
            <option value="">All</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        <button onClick={() => load()} className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded hover:bg-gray-50">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
        {data && <span className="ml-auto text-xs text-gray-400">{data.total} session{data.total !== 1 ? 's' : ''}</span>}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-12">
          <Loader2 className="w-7 h-7 animate-spin text-blue-500" />
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Empty */}
      {!loading && !error && data?.results.length === 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-12 flex flex-col items-center gap-3 shadow-sm text-gray-400">
          <AlertTriangle className="w-10 h-10" />
          <p className="text-sm">No sessions found matching these filters.</p>
        </div>
      )}

      {/* Table */}
      {!loading && !error && data && data.results.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">ID</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Source</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">File</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Timestamp</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Detections</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Classes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.results.map(s => (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{s.id}</td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1.5 capitalize">
                        {SOURCE_ICON[s.source_type]}
                        {s.source_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600 max-w-[140px] truncate" title={s.filename ?? ''}>
                      {s.filename ?? <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">{formatDate(s.created_at)}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[s.status] ?? 'bg-gray-100 text-gray-600'}`}>
                        {s.status}
                      </span>
                      {s.error_message && (
                        <p className="text-red-500 text-xs mt-0.5 truncate max-w-[120px]" title={s.error_message}>{s.error_message}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-800 font-medium">{s.total_detections}</td>
                    <td className="px-4 py-3">
                      {Object.keys(s.ppe_counts || {}).length === 0
                        ? <span className="text-gray-300 text-xs">none</span>
                        : (
                          <div className="flex flex-wrap gap-1">
                            {Object.entries(s.ppe_counts || {}).slice(0, 4).map(([cls, n]) => (
                              <span key={cls} className="px-1.5 py-0.5 bg-teal-50 text-teal-700 text-xs rounded border border-teal-100">
                                {cls}:{n}
                              </span>
                            ))}
                          </div>
                        )
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="border-t border-gray-100 px-4 py-3 flex items-center justify-between text-sm text-gray-500">
              <span>Page {page + 1} of {totalPages}</span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="p-1 rounded hover:bg-gray-100 disabled:opacity-30"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                  className="p-1 rounded hover:bg-gray-100 disabled:opacity-30"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default History;
