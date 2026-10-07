// Configurable API base URL for SafeVision AI
// Locally: defaults to http://127.0.0.1:8000/api
// Deployed (e.g., Vercel): configured via VITE_API_URL environment variable

const RAW_API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// Strip any trailing slashes
const cleanUrl = RAW_API_URL.replace(/\/+$/, '');

// Ensure /api path prefix is present so all existing endpoints remain unchanged
export const API_BASE = cleanUrl.endsWith('/api') ? cleanUrl : `${cleanUrl}/api`;
