/**
 * Unified Frontend Gateway & Proxy
 * 
 * This server:
 * 1. Serves the React frontend as the primary interface
 * 2. Proxies all /api/* requests to the FastAPI backend (port 8000)
 * 3. Provides a single entry point for users
 * 
 * Installation:
 * npm install express http-proxy dotenv
 * 
 * Run:
 * node server.js
 */

import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import httpProxy from 'http-proxy';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const FRONTEND_PORT = process.env.FRONTEND_PORT || 3000;
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// Middleware
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));

// Create proxy instance
const proxy = httpProxy.createProxyServer({});

// Handle proxy errors
proxy.on('error', (err, req, res) => {
  console.error('Proxy error:', err.message);
  res.status(503).json({
    error: 'Backend service unavailable',
    message: 'Please ensure the FastAPI backend is running on ' + BACKEND_URL
  });
});

// Serve static React frontend from dist folder
const distPath = path.join(__dirname, 'MLR_UI_React', 'dist');
app.use(express.static(distPath));

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({ status: 'Frontend gateway is running', backend: BACKEND_URL });
});

// Proxy all /api/* requests to FastAPI backend
app.all('/api/*', (req, res) => {
  // Forward to backend
  proxy.web(req, res, { target: BACKEND_URL, changeOrigin: true });
});

// Fallback: Serve React app for all other routes (SPA routing)
app.get('*', (req, res) => {
  res.sendFile(path.join(distPath, 'index.html'));
});

app.listen(FRONTEND_PORT, () => {
  console.log(`✅ Frontend gateway running at http://localhost:${FRONTEND_PORT}`);
});
