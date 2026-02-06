/**
 * WebSocket utility for real-time job status updates
 * 
 * This provides instant status updates instead of HTTP polling.
 * Falls back to polling if WebSocket connection fails.
 */

class JobWebSocket {
    constructor(baseUrl = null) {
        // Convert HTTP URL to WebSocket URL
        const httpBase = baseUrl || import.meta.env.VITE_API_URL ||
            (import.meta.env.DEV ? 'http://localhost:8000' : 'https://mlr-backend.onrender.com');

        this.wsBase = httpBase.replace('http://', 'ws://').replace('https://', 'wss://');
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        this.jobCompleted = false;  // Track if job finished to prevent unnecessary reconnects
    }

    /**
     * Connect to a job's WebSocket stream
     * @param {string} jobId - The job ID to monitor
     * @param {function} onStatus - Callback for status updates
     * @param {function} onComplete - Callback when job completes
     * @param {function} onError - Callback for errors
     * @returns {function} Cleanup function to close the connection
     */
    connect(jobId, { onStatus, onComplete, onError }) {
        const wsUrl = `${this.wsBase}/ws/job/${jobId}`;
        console.log('[WS] Connecting to:', wsUrl);

        // Reset state for new connection
        this.jobCompleted = false;

        try {
            this.socket = new WebSocket(wsUrl);

            this.socket.onopen = () => {
                console.log('[WS] Connected to job:', jobId);
                this.reconnectAttempts = 0;
            };

            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('[WS] Status update:', data);

                    // Call status callback
                    if (onStatus) {
                        onStatus(data);
                    }

                    // Check if job is complete
                    if (data.status === 'completed' || data.final) {
                        console.log('[WS] Job completed, closing connection');
                        this.jobCompleted = true;  // Flag to prevent reconnect
                        if (onComplete) {
                            onComplete(data);
                        }
                        // Close the socket cleanly after job completes
                        this.disconnect();
                    } else if (data.status === 'failed') {
                        console.log('[WS] Job failed');
                        this.jobCompleted = true;  // Flag to prevent reconnect
                        if (onError) {
                            onError(new Error(data.message || 'Job failed'));
                        }
                        this.disconnect();
                    }
                } catch (parseError) {
                    console.error('[WS] Failed to parse message:', parseError);
                }
            };

            this.socket.onerror = (error) => {
                console.error('[WS] WebSocket error:', error);
                if (onError) {
                    onError(error);
                }
            };

            this.socket.onclose = (event) => {
                console.log('[WS] Connection closed:', event.code, event.reason);

                // Don't reconnect if job already completed/failed
                if (this.jobCompleted) {
                    console.log('[WS] Job finished, not reconnecting');
                    return;
                }

                // Auto-reconnect if not a clean close and under max attempts
                if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    console.log(`[WS] Reconnecting... attempt ${this.reconnectAttempts}`);
                    setTimeout(() => {
                        this.connect(jobId, { onStatus, onComplete, onError });
                    }, 1000 * this.reconnectAttempts);
                }
            };

            // Return cleanup function
            return () => this.disconnect();

        } catch (error) {
            console.error('[WS] Failed to create WebSocket:', error);
            if (onError) {
                onError(error);
            }
            return () => { };
        }
    }

    /**
     * Disconnect the WebSocket
     */
    disconnect() {
        if (this.socket) {
            console.log('[WS] Disconnecting...');
            this.socket.close(1000, 'Client disconnect');
            this.socket = null;
        }
    }

    /**
     * Check if WebSocket is currently connected
     */
    isConnected() {
        return this.socket && this.socket.readyState === WebSocket.OPEN;
    }
}

// Export singleton instance
export const jobWebSocket = new JobWebSocket();

/**
 * React hook for using WebSocket with a job
 * 
 * Usage:
 * const { status, isConnected } = useJobWebSocket(jobId, onComplete);
 */
export function useJobWebSocket(jobId, onComplete) {
    // This is a placeholder - will be used if you want React hook integration
    // For now, use jobWebSocket.connect() directly
    return { jobWebSocket };
}
