// Centralized API configuration for development and production
// During development, Vite proxy routes empty/relative paths to http://localhost:8000
// In production, we use the VITE_API_URL environment variable, or fallback to empty string (same domain)
export const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export function getApiUrl(path: string): string {
  // Remove leading slash if present to avoid double slashes
  const cleanPath = path.startsWith("/") ? path.slice(1) : path;
  
  if (!API_BASE_URL) {
    return `/${cleanPath}`;
  }
  
  return `${API_BASE_URL}/${cleanPath}`;
}
