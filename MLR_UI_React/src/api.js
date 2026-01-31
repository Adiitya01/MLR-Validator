// API Configuration - Connects to FastAPI backend
// Backend runs on http://localhost:8000

class APIClient {
  constructor(baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000',) {
    console.log('[DEBUG] APIClient initialized with baseUrl:', baseUrl);
    this.baseUrl = baseUrl;
    this.isConnected = false;
  }

  // Expose baseURL for external use (e.g., in fetch calls)
  get baseURL() {
    return this.baseUrl;
  }

  // Test backend connection on app start
  async testConnection() {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      if (response.ok) {
        this.isConnected = true;
        return true;
      }
    } catch (error) {
      this.isConnected = false;
    }
    return false;
  }

  // Fetch validation results by brochure_id
  async getResults(brochureId) {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${this.baseUrl}/validation-results/${brochureId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!response.ok) {
        throw new Error(`Failed to fetch results: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      throw error;
    }
  }

  // Get all brochures (history)
  async getBrochures() {
    try {
      const response = await fetch(`${this.baseUrl}/brochures`);
      if (!response.ok) {
        throw new Error(`Failed to fetch brochures: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error fetching history:', error);
      return [];
    }
  }

  // Check status of a background job
  async checkJobStatus(jobId) {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${this.baseUrl}/job-status/${jobId}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (!response.ok) {
        throw new Error(`Status check failed: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      throw error;
    }
  }

  // Run full pipeline: Starts a background job and returns job_id
  async runPipeline(brochureFile, referenceFiles, validationType = 'research') {
    if (!this.isConnected && !await this.testConnection()) {
      throw new Error('Backend not connected. Please start the backend first.');
    }

    const formData = new FormData();
    formData.append('brochure_pdf', brochureFile);

    // Add all reference files
    referenceFiles.forEach((file) => {
      formData.append('reference_pdfs', file);
    });

    // Add validation type
    formData.append('validation_type', validationType);

    try {
      const options = {
        method: 'POST',
        body: formData
      };

      // Add auth token if available
      const token = localStorage.getItem('access_token');
      if (token) {
        options.headers = {
          'Authorization': `Bearer ${token}`
        };
      }

      console.log(`[DEBUG] Starting Job via ${this.baseUrl}/run-pipeline`);
      const response = await fetch(`${this.baseUrl}/run-pipeline`, options);

      if (response.status === 401) {
        console.error('[AUTH] Token expired or invalid. Redirecting to login...');
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_data');
        window.location.href = '/login?expired=true';
        throw new Error('Session expired. Please log in again.');
      }

      if (!response.ok) {
        let errorDetail = '';
        try {
          const errorJson = await response.json();
          errorDetail = errorJson.detail || JSON.stringify(errorJson);
        } catch (e) {
          errorDetail = await response.text();
        }
        throw new Error(`API error: ${response.status} - ${errorDetail || response.statusText}`);
      }

      const data = await response.json();
      if (!data.job_id) {
        throw new Error('No job_id in response');
      }

      return data.job_id;
    } catch (error) {
      throw error;
    }
  }
}

// Export singleton instance
export const apiClient = new APIClient();
