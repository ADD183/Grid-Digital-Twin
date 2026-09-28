/**
 * Dynamic API Base URL Configuration for VoltPredict Frontend.
 * Reads environment variable VITE_API_BASE_URL when deployed (e.g., on Vercel),
 * falling back to local backend port 8000 during local development.
 */
export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
