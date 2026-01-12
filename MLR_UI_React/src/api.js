// API Configuration - Connects to FastAPI backend
// Backend runs on http://localhost:8000

class APIClient {
  constructor(baseUrl = import.meta.env.REACT_APP_API_URL || 'http://localhost:8000') {
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
      const response = await fetch(`${this.baseUrl}/results/${brochureId}`);
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

  // Run full pipeline: Extract + Validate in one call
  async runPipeline(brochureFile, referenceFiles, validationType = 'research', onProgress, onResult) {
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
      const token = localStorage.getItem('token');
      if (token) {
        options.headers = {
          'Authorization': `Bearer ${token}`
        };
      }

      const response = await fetch(`${this.baseUrl}/run-pipeline`, options);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();

      if (!data.results) {
        throw new Error('No validation results in response');
      }

      // Return all results
      return data.results;

    } catch (error) {
      throw error;
    }
  }
}

// Export singleton instance
export const apiClient = new APIClient();
