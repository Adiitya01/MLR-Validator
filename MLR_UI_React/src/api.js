// API Configuration - Connects to Django DRF backend
// Backend runs on http://localhost:8000

class APIClient {
  constructor(baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000',) {
    console.log('[DEBUG] APIClient initialized with baseUrl:', baseUrl);
    this.baseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    this.isConnected = false;

    // API Prefixes
    this.validatorPath = '/api/validator';
    this.authPath = '/api/auth';
  }

  // Expose baseURL for external use
  get baseURL() {
    return this.baseUrl;
  }

  // Test backend connection on app start
  async testConnection() {
    try {
      const response = await fetch(`${this.baseUrl}${this.validatorPath}/health/`);
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
      const response = await fetch(`${this.baseUrl}${this.validatorPath}/results/${brochureId}/`, {
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
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${this.baseUrl}${this.validatorPath}/history/`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
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
      const response = await fetch(`${this.baseUrl}${this.validatorPath}/job-status/${jobId}/`, {
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

    referenceFiles.forEach((file) => {
      formData.append('reference_pdfs', file);
    });

    formData.append('validation_type', validationType);

    try {
      const token = localStorage.getItem('access_token');
      const options = {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      };

      console.log(`[DEBUG] Starting Job via ${this.baseUrl}${this.validatorPath}/run-pipeline/`);
      const response = await fetch(`${this.baseUrl}${this.validatorPath}/run-pipeline/`, options);

      if (response.status === 401) {
        this.handleAuthError();
        throw new Error('Session expired. Please log in again.');
      }

      if (!response.ok) {
        const errorJson = await response.json().catch(() => ({}));
        throw new Error(errorJson.detail || `API error: ${response.status}`);
      }

      const data = await response.json();
      return data.job_id;
    } catch (error) {
      throw error;
    }
  }

  // Manual Review
  async runManualReview(statement, referencePdfs, referenceNo = null) {
    const formData = new FormData();
    formData.append('statement', statement);
    if (referenceNo) formData.append('reference_no', referenceNo);

    referencePdfs.forEach(file => {
      formData.append('reference_pdfs', file);
    });

    const token = localStorage.getItem('access_token');
    const response = await fetch(`${this.baseUrl}${this.validatorPath}/manual-review/`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      },
      body: formData
    });

    if (!response.ok) {
      const errorJson = await response.json().catch(() => ({}));
      throw new Error(errorJson.detail || 'Manual review failed');
    }

    return await response.json();
  }

  handleAuthError() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_data');
    window.location.href = '/login?expired=true';
  }
}

export const apiClient = new APIClient();
