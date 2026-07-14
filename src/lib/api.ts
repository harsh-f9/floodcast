// Centralized API configuration for development and production
// During development, Vite proxy routes empty/relative paths to http://localhost:8000
// In production, we use the VITE_API_URL environment variable, or fallback to the render backend URL
export const API_BASE_URL = import.meta.env.VITE_API_URL || "https://floodcast-backend-vx1j.onrender.com";

export function getApiUrl(path: string): string {
  // Remove leading slash if present to avoid double slashes
  const cleanPath = path.startsWith("/") ? path.slice(1) : path;
  
  if (!API_BASE_URL) {
    return `/${cleanPath}`;
  }
  
  return `${API_BASE_URL}/${cleanPath}`;
}
