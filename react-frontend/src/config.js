/**
 * API Configuration
 * 
 * In development: Uses relative paths (proxied by Vite to localhost:5050)
 * In production (Amplify): Uses the EC2 instance IP
 */

const isDevelopment = import.meta.env.MODE === 'development'

// Get the API base URL from environment variable, or use defaults
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (
  isDevelopment 
    ? '' // Empty string uses relative paths (via Vite proxy)
    : 'http://54.145.3.50:5050' // Production: EC2 instance
)

/**
 * Build a full API URL
 * @param {string} path - API path (e.g., '/api/card_stats')
 * @returns {string} Full URL for the API endpoint
 */
export function getApiUrl(path) {
  return API_BASE_URL + path
}

export default { API_BASE_URL, getApiUrl }
