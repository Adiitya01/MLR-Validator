import React, { useState } from 'react';
import '../styles/Auth.css';
import logo from '../assets/ethosh-logo.svg';

export default function LoginForm({ onSuccess }) {
  const [formData, setFormData] = useState({
    email: '',
    password: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [userData, setUserData] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    setError('');
  };

  const validateForm = () => {
    if (!formData.email.trim()) {
      setError('Email is required');
      return false;
    }
    if (!formData.password.trim()) {
      setError('Password is required');
      return false;
    }
    return true;
  };

  const handleLogin = async (e) => {
    e.preventDefault();

    if (!validateForm()) return;

    setLoading(true);
    setError('');

    try {
      const apiBaseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseURL}/api/auth/login/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: formData.email.trim(),
          password: formData.password
        })
      });

      const data = await response.json();

      if (!response.ok) {
        setError(data.detail || 'Login failed. Please try again.');
        return;
      }

      // Store token and user data
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user_data', JSON.stringify(data.user));

      setUserData(data.user);
      setSuccess(true);

      // Redirect to dashboard after 2 seconds
      setTimeout(() => {
        if (onSuccess) {
          onSuccess(data.user, data.access_token);
        } else {
          window.location.href = '/dashboard';
        }
      }, 2000);
    } catch (err) {
      console.error('Login error:', err);
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-container">
        <img src={logo} alt="Logo" className="auth-logo-top" />
        <div className="auth-card success" style={{ textAlign: 'center', color: 'white' }}>
          <div className="success-icon" style={{ fontSize: '64px', marginBottom: '20px' }}>✓</div>
          <h2 style={{ margin: '0 0 10px 0', fontSize: '24px' }}>Welcome Back!</h2>
          <p style={{ margin: '0 0 20px 0', fontSize: '16px' }}>
            {userData?.full_name || userData?.email}
          </p>
          <p style={{ margin: 0, fontSize: '14px', opacity: 0.9 }}>
            Redirecting to dashboard...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      {/* Logo in top right corner */}
      <img src={logo} alt="Logo" className="auth-logo-top" />

      <div className="auth-card">
        <div className="auth-header">
          <h1>Welcome Back</h1>
          <p>Sign in to continue to MLR Validator</p>
        </div>

        <form className="auth-form" onSubmit={handleLogin}>
          {error && <div className="form-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              name="email"
              className="form-input"
              placeholder="your@email.com"
              value={formData.email}
              onChange={handleChange}
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              name="password"
              className="form-input"
              placeholder="Enter your password"
              value={formData.password}
              onChange={handleChange}
              disabled={loading}
            />
          </div>

          <div className="form-group" style={{ textAlign: 'right', marginTop: '-15px', marginBottom: '20px' }}>
            <a href="/forgot-password" style={{ fontSize: '13px', color: '#60a5fa', textDecoration: 'none', fontWeight: 500 }}>
              Forgot Password?
            </a>
          </div>

          <button
            type="submit"
            className="form-button"
            disabled={loading}
          >
            {loading ? (
              <>
                <div className="spinner"></div>
                Signing In...
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        <div className="auth-footer">
          <p>Don't have an account? <a href="/signup">Sign up here</a></p>
        </div>
      </div>
    </div>
  );
}
