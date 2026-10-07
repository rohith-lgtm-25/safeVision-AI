import React, {
  useState,
  useRef,
  useEffect,
  useCallback,
} from 'react';
import axios from 'axios';
import {
  Camera,
  CameraOff,
  Loader2,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { API_BASE } from '../config';

// How long (ms) to wait between frame captures.
// Default 150 ms (~6.7 FPS inference rate). Native video remains 30 FPS.
const DEFAULT_INTERVAL_MS = 150;
const MIN_INTERVAL_MS = 100;
const MAX_INTERVAL_MS = 2000;


type PermState = 'unknown' | 'granted' | 'denied' | 'error';

const WebcamMonitor: React.FC = () => {
  // ── Refs ────────────────────────────────────────────────────────────────
  const videoRef    = useRef<HTMLVideoElement>(null);
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const streamRef   = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const inFlightRef = useRef(false);   // prevents overlapping requests

  // ── State ───────────────────────────────────────────────────────────────
  const [permState,  setPermState]  = useState<PermState>('unknown');
  const [monitoring, setMonitoring] = useState(false);
  const [annotated,  setAnnotated]  = useState<string | null>(null);
  const [ppeCounts,  setPpeCounts]  = useState<Record<string, number>>({});
  const [error,      setError]      = useState<string | null>(null);
  const [fps,        setFps]        = useState(DEFAULT_INTERVAL_MS);
  const [inferring,  setInferring]  = useState(false);

  // ── Session tracking ────────────────────────────────────────────────────
  const sessionDataRef = useRef({
    startTime: 0,
    framesSent: 0,
    accumulatedPpeCounts: {} as Record<string, number>,
  });

  const submitSessionSummary = async () => {
    if (sessionDataRef.current.startTime > 0) {
      const duration = (Date.now() - sessionDataRef.current.startTime) / 1000;
      const totalDetections = Object.values(sessionDataRef.current.accumulatedPpeCounts)
        .reduce((s, c) => s + c, 0);

      const payload = {
        total_frames_sent: sessionDataRef.current.framesSent,
        total_detections: totalDetections,
        class_counts: sessionDataRef.current.accumulatedPpeCounts,
        ppe_counts: sessionDataRef.current.accumulatedPpeCounts,
        duration_seconds: duration,
      };

      // Reset to prevent duplicate submissions
      sessionDataRef.current.startTime = 0;

      try {
        await axios.post(`${API_BASE}/history/webcam`, payload);
      } catch (err) {
        console.error('Failed to save webcam session summary', err);
      }
    }
  };

  // ── Cleanup on unmount ──────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      _stopAll();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Start webcam ────────────────────────────────────────────────────────
  const startWebcam = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 640 },
          height: { ideal: 480 },
        },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setPermState('granted');
    } catch (err: any) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setPermState('denied');
        setError(
          'Camera permission was denied. Please allow camera access in your browser settings and reload the page.',
        );
      } else {
        setPermState('error');
        setError(`Could not access camera: ${err.message}`);
      }
    }
  }, []);

  // ── Stop everything ─────────────────────────────────────────────────────
  const _stopAll = () => {
    submitSessionSummary();
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    inFlightRef.current = false;
    setMonitoring(false);
    setInferring(false);
  };

  // ── Capture one frame and send to backend ────────────────────────────────
  const captureAndInfer = useCallback(async () => {
    // Guard: skip if a request is already in-flight or video isn't ready
    if (inFlightRef.current) return;
    const video = videoRef.current;
    if (!video || video.readyState < 2) return;

    inFlightRef.current = true;
    setInferring(true);

    try {
      // Use ref canvas or create offscreen canvas scaled to max 640px
      const MAX_WIDTH = 640;
      const scale = Math.min(1, MAX_WIDTH / video.videoWidth);
      const targetW = Math.round(video.videoWidth * scale);
      const targetH = Math.round(video.videoHeight * scale);

      let canvas = canvasRef.current;
      if (!canvas) {
        canvas = document.createElement('canvas');
      }
      canvas.width = targetW;
      canvas.height = targetH;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, targetW, targetH);

      // Convert canvas to JPEG Blob with quality=0.75 for fast transmission
      const blob: Blob = await new Promise((resolve, reject) => {
        canvas!.toBlob(
          b => (b ? resolve(b) : reject(new Error('Canvas toBlob failed'))),
          'image/jpeg',
          0.75,
        );
      });

      const formData = new FormData();
      formData.append('file', blob, 'frame.jpg');

      const res = await axios.post<{
        status: string;
        image: string;
        ppe_counts: Record<string, number>;
      }>(`${API_BASE}/detect/frame`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 5_000,
      });

      if (res.data.status === 'success') {
        setAnnotated(res.data.image);
        const newPpeCounts = res.data.ppe_counts || {};
        setPpeCounts(newPpeCounts);

        sessionDataRef.current.framesSent += 1;
        Object.entries(newPpeCounts).forEach(([cls, count]) => {
          sessionDataRef.current.accumulatedPpeCounts[cls] =
            (sessionDataRef.current.accumulatedPpeCounts[cls] || 0) + (count as number);
        });

        setError(null);
      }
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Inference failed';
      setError(`Frame error: ${msg}`);
    } finally {
      inFlightRef.current = false;
      setInferring(false);
    }
  }, []);

  // ── Start monitoring ────────────────────────────────────────────────────
  const handleStart = useCallback(async () => {
    // Make sure camera is initialised
    if (!streamRef.current) {
      await startWebcam();
    }
    // Exit if permission was denied inside startWebcam
    if (!streamRef.current) return;

    setMonitoring(true);
    setAnnotated(null);
    setPpeCounts({});
    setError(null);

    // Initialize session tracking
    sessionDataRef.current = {
      startTime: Date.now(),
      framesSent: 0,
      accumulatedPpeCounts: {},
    };

    intervalRef.current = setInterval(captureAndInfer, fps);
  }, [startWebcam, captureAndInfer, fps]);

  // ── Stop monitoring (keep webcam preview live) ──────────────────────────
  const handleStop = useCallback(() => {
    submitSessionSummary();
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    inFlightRef.current = false;
    setMonitoring(false);
    setInferring(false);
  }, []);

  // ── Re-request camera permission ─────────────────────────────────────────
  const handleRetryPermission = useCallback(async () => {
    setPermState('unknown');
    setError(null);
    _stopAll();
    await startWebcam();
  }, [startWebcam]);

  // ── Update interval if changed while monitoring ─────────────────────────
  useEffect(() => {
    if (!monitoring) return;
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(captureAndInfer, fps);
  }, [fps, monitoring, captureAndInfer]);

  // ── Request camera on mount ──────────────────────────────────────────────
  useEffect(() => {
    startWebcam();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isGranted = permState === 'granted';

  return (
    <div className="space-y-6">

      {/* ── Camera / Controls card ───────────────────────────────────────── */}
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <h3 className="text-lg font-medium text-gray-900 flex items-center gap-2">
            <Camera className="w-5 h-5 text-blue-500" />
            Live Webcam Feed
          </h3>

          {/* Interval control */}
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>Capture every</span>
            <input
              type="number"
              min={MIN_INTERVAL_MS}
              max={MAX_INTERVAL_MS}
              step={50}
              value={fps}
              onChange={e => setFps(Math.max(MIN_INTERVAL_MS, Math.min(MAX_INTERVAL_MS, Number(e.target.value))))}
              className="w-20 px-2 py-1 border border-gray-300 rounded text-center"
              disabled={monitoring}
            />
            <span>ms</span>
          </div>

          {/* Start / Stop buttons */}
          <div className="flex gap-2">
            {!monitoring ? (
              <button
                onClick={handleStart}
                disabled={!isGranted}
                className="flex items-center gap-1.5 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Camera className="w-4 h-4" />
                Start Monitoring
              </button>
            ) : (
              <button
                onClick={handleStop}
                className="flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-md hover:bg-red-700"
              >
                <CameraOff className="w-4 h-4" />
                Stop
              </button>
            )}
          </div>
        </div>

        {/* ── Error banner ─────────────────────────────────────────────── */}
        {error && (
          <div className="mb-4 flex items-start gap-2 p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span className="flex-1">{error}</span>
            {permState === 'denied' && (
              <button
                onClick={handleRetryPermission}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-red-100 hover:bg-red-200 rounded"
              >
                <RefreshCw className="w-3 h-3" />
                Retry
              </button>
            )}
          </div>
        )}

        {/* ── Video grid ───────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

          {/* Live preview */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-gray-700">Live Preview</p>
              {inferring && (
                <span className="flex items-center gap-1 text-xs text-blue-600">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Inferring…
                </span>
              )}
            </div>
            {isGranted ? (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full rounded-lg border border-gray-200 bg-black"
              />
            ) : (
              <div className="w-full h-48 flex flex-col items-center justify-center bg-gray-100 rounded-lg border border-gray-200 gap-2">
                <CameraOff className="w-8 h-8 text-gray-400" />
                <p className="text-sm text-gray-500">
                  {permState === 'denied'
                    ? 'Camera access denied'
                    : permState === 'error'
                    ? 'Camera error'
                    : 'Requesting camera…'}
                </p>
              </div>
            )}
          </div>

          {/* Annotated result */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">Annotated Frame</p>
            {annotated ? (
              <img
                src={annotated}
                alt="Annotated frame"
                className="w-full rounded-lg border border-gray-200"
              />
            ) : (
              <div className="w-full h-48 flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200">
                <p className="text-sm text-gray-400">
                  {monitoring ? 'Waiting for first frame…' : 'Start monitoring to see results'}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Hidden canvas used for frame capture — never shown */}
        <canvas ref={canvasRef} className="hidden" />
      </div>

      {/* ── Detection counts card ─────────────────────────────────────────── */}
      {Object.keys(ppeCounts).length > 0 && (
        <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
          <h4 className="text-sm font-semibold text-gray-500 uppercase mb-3">
            PPE Detections — Last Frame
          </h4>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ppeCounts).map(([cls, n]) => (
              <span
                key={cls}
                className="px-3 py-1 bg-teal-50 text-teal-700 text-sm rounded-full border border-teal-200"
              >
                {cls}: {n}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Hidden canvas for capturing video frames */}
      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
};

export default WebcamMonitor;
