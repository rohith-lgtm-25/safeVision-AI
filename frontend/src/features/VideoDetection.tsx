import React, { useState, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Upload, Loader2, CheckCircle, AlertCircle, Download, Play } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';
const POLL_INTERVAL_MS = 2000;
const ALLOWED_TYPES = ['video/mp4', 'video/quicktime', 'video/x-msvideo'];
const ALLOWED_EXTS = ['.mp4', '.mov', '.avi'];
const MAX_SIZE_BYTES = 100 * 1024 * 1024; // 100 MB

type JobStatus = 'idle' | 'uploading' | 'queued' | 'processing' | 'completed' | 'failed';

interface StatusResponse {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  class_counts: Record<string, number>;
  error: string | null;
}

const VideoDetection: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [classCounts, setClassCounts] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [frameInterval, setFrameInterval] = useState(5);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Cleanup polling on unmount ────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // ── Poll job status ───────────────────────────────────────────────────────
  const startPolling = useCallback((id: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await axios.get<StatusResponse>(`${API_BASE}/detect/video/${id}/status`);
        const data = res.data;
        setProgress(data.progress);
        setClassCounts(data.class_counts || {});
        setJobStatus(data.status as JobStatus);

        if (data.status === 'completed') {
          clearInterval(pollRef.current!);
          // Build a URL that streams the result from the backend
          setResultUrl(`${API_BASE}/detect/video/${id}/result`);
        } else if (data.status === 'failed') {
          clearInterval(pollRef.current!);
          setError(data.error || 'Processing failed for an unknown reason.');
        }
      } catch (err: any) {
        clearInterval(pollRef.current!);
        setError('Lost connection while polling job status.');
        setJobStatus('failed');
      }
    }, POLL_INTERVAL_MS);
  }, []);

  // ── File selection ────────────────────────────────────────────────────────
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side type validation
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_TYPES.includes(file.type) && !ALLOWED_EXTS.includes(ext)) {
      setError('Unsupported file type. Please upload an MP4, MOV, or AVI video.');
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      setError('File exceeds the 100 MB size limit.');
      return;
    }

    setSelectedFile(file);
    setJobId(null);
    setJobStatus('idle');
    setProgress(0);
    setClassCounts({});
    setError(null);
    setResultUrl(null);
  };

  // ── Upload & start job ────────────────────────────────────────────────────
  const handleUpload = async () => {
    if (!selectedFile) return;
    setError(null);
    setJobStatus('uploading');
    setProgress(0);
    setResultUrl(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await axios.post<{ job_id: string; status: string }>(
        `${API_BASE}/detect/video?frame_interval=${frameInterval}`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      );
      const id = res.data.job_id;
      setJobId(id);
      setJobStatus('queued');
      startPolling(id);
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message;
      setError(`Upload failed: ${detail}`);
      setJobStatus('failed');
    }
  };

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setSelectedFile(null);
    setJobId(null);
    setJobStatus('idle');
    setProgress(0);
    setClassCounts({});
    setError(null);
    setResultUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Derived helpers ───────────────────────────────────────────────────────
  const isProcessing = jobStatus === 'uploading' || jobStatus === 'queued' || jobStatus === 'processing';
  const statusLabel: Record<JobStatus, string> = {
    idle: '',
    uploading: 'Uploading…',
    queued: 'Queued — waiting for worker…',
    processing: `Processing… ${progress}%`,
    completed: 'Completed',
    failed: 'Failed',
  };

  return (
    <div className="space-y-6">
      {/* ── Upload Panel ─────────────────────────────────────────────────── */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h3 className="text-lg font-medium text-gray-900 mb-1">Upload Video for Detection</h3>

        {/* Drop zone */}
        <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100">
          <Upload className="w-10 h-10 mb-3 text-gray-400" />
          <p className="text-sm text-gray-500">
            <span className="font-semibold">Click to upload</span> or drag and drop
          </p>
          <p className="text-xs text-gray-400 mt-1">MP4, MOV, AVI — max 100 MB</p>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".mp4,.mov,.avi,video/mp4,video/quicktime,video/x-msvideo"
            onChange={handleFileChange}
            disabled={isProcessing}
          />
        </label>

        {/* Frame interval control */}
        {!isProcessing && !resultUrl && (
          <div className="mt-4 flex items-center gap-3">
            <label className="text-sm text-gray-600 whitespace-nowrap">
              Process every{' '}
              <input
                type="number"
                min={1}
                max={30}
                value={frameInterval}
                onChange={e => setFrameInterval(Number(e.target.value))}
                className="w-14 mx-1 px-2 py-1 border border-gray-300 rounded text-center text-sm"
              />{' '}
              frames
            </label>
            <span className="text-xs text-gray-400">(lower = more detections, slower)</span>
          </div>
        )}

        {/* Selected file + action buttons */}
        {selectedFile && (
          <div className="mt-4 flex flex-wrap justify-between items-center gap-3 bg-gray-50 p-4 rounded-md">
            <span className="text-sm text-gray-700 truncate max-w-xs">{selectedFile.name}</span>
            <div className="flex gap-2">
              {!isProcessing && !resultUrl && (
                <button
                  onClick={handleUpload}
                  className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700"
                >
                  Run Detection
                </button>
              )}
              <button
                onClick={handleReset}
                className="px-4 py-2 bg-gray-200 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-300"
              >
                Reset
              </button>
            </div>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div className="mt-4 flex items-start gap-2 p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* ── Progress Panel ───────────────────────────────────────────────── */}
      {(isProcessing || jobStatus === 'completed' || jobStatus === 'failed') && (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center gap-3 mb-4">
            {isProcessing && <Loader2 className="w-5 h-5 animate-spin text-blue-500" />}
            {jobStatus === 'completed' && <CheckCircle className="w-5 h-5 text-green-500" />}
            {jobStatus === 'failed' && <AlertCircle className="w-5 h-5 text-red-500" />}
            <span className="text-sm font-medium text-gray-700">{statusLabel[jobStatus]}</span>
            {jobId && <span className="ml-auto text-xs text-gray-400 font-mono">{jobId.slice(0, 8)}</span>}
          </div>

          {/* Progress bar */}
          {(isProcessing || jobStatus === 'completed') && (
            <div className="w-full bg-gray-200 rounded-full h-2 mb-4">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          )}

          {/* Detection counts */}
          {Object.keys(classCounts).length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">Detections so far</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(classCounts).map(([cls, count]) => (
                  <span
                    key={cls}
                    className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded-full border border-blue-200"
                  >
                    {cls}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Result Panel ─────────────────────────────────────────────────── */}
      {resultUrl && (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
              <Play className="w-5 h-5 text-green-500" />
              Annotated Result
            </h3>
            <a
              href={resultUrl}
              download={`safevision_${jobId?.slice(0, 8)}_annotated.mp4`}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700"
            >
              <Download className="w-4 h-4" />
              Download
            </a>
          </div>

          <video
            ref={videoRef}
            src={resultUrl}
            controls
            className="w-full rounded-lg border border-gray-200 max-h-[500px]"
          >
            Your browser does not support HTML5 video.
          </video>
        </div>
      )}
    </div>
  );
};

export default VideoDetection;
