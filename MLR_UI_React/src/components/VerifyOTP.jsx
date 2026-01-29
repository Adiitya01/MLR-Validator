import React, { useState, useEffect } from 'react';
import '../styles/Auth.css';
import logo from '../assets/ethosh-logo.svg';

export default function VerifyOTP() {
    const [otp, setOtp] = useState('');
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [resending, setResending] = useState(false);
    const [cooldown, setCooldown] = useState(0);
    const [userData, setUserData] = useState(null);

    useEffect(() => {
        const data = localStorage.getItem('user_data');
        if (data) {
            const parsed = JSON.parse(data);
            setUserData(parsed);
            // Auto-send OTP on first load
            sendOTP(parsed.email);
        } else {
            window.location.href = '/login';
        }
    }, []);

    useEffect(() => {
        if (cooldown > 0) {
            const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [cooldown]);

    const sendOTP = async (email) => {
        if (cooldown > 0) return;
        setResending(true);
        setError('');
        try {
            const apiBaseURL = import.meta.env.VITE_API_URL || 'https://mlr-backend-api.onrender.com';
            const response = await fetch(`${apiBaseURL}/auth/send-otp`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            const data = await response.json();
            if (response.ok) {
                setMessage('OTP sent to your email');
                setCooldown(60);
            } else {
                setError(data.detail || 'Failed to send OTP');
            }
        } catch (err) {
            setError('Network error. Please try again.');
        } finally {
            setResending(false);
        }
    };

    const handleVerify = async (e) => {
        e.preventDefault();
        if (otp.length !== 6) {
            setError('Please enter a 6-digit code');
            return;
        }

        setLoading(true);
        setError('');
        setMessage('');

        try {
            const apiBaseURL = import.meta.env.VITE_API_URL || 'https://mlr-backend-api.onrender.com';
            const response = await fetch(`${apiBaseURL}/auth/verify-otp`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: userData.email, otp })
            });
            const data = await response.json();

            if (response.ok) {
                // Update local storage
                const updatedUser = { ...userData, is_email_verified: true };
                localStorage.setItem('user_data', JSON.stringify(updatedUser));
                setMessage('Email verified! Redirecting...');
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1500);
            } else {
                setError(data.detail || 'Verification failed');
            }
        } catch (err) {
            setError('Network error. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-container">
            <img src={logo} alt="Logo" className="auth-logo-top" />
            <div className="auth-card">
                <div className="auth-header">
                    <h1>Verify Email</h1>
                    <p>We've sent a 6-digit code to <strong>{userData?.email}</strong></p>
                </div>

                <form className="auth-form" onSubmit={handleVerify}>
                    {error && <div className="form-error">{error}</div>}
                    {message && <div style={{ color: '#10b981', textAlign: 'center', fontSize: '14px', marginBottom: '10px' }}>{message}</div>}

                    <div className="form-group">
                        <label htmlFor="otp">Enter 6-Digit Code</label>
                        <input
                            id="otp"
                            type="text"
                            name="otp"
                            className="form-input"
                            placeholder="000000"
                            maxLength="6"
                            value={otp}
                            onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                            disabled={loading}
                            autoFocus
                            style={{ textAlign: 'center', fontSize: '24px', letterSpacing: '0.3em' }}
                        />
                    </div>

                    <button type="submit" className="form-button" disabled={loading || otp.length !== 6}>
                        {loading ? <div className="spinner"></div> : 'Verify Code'}
                    </button>
                </form>

                <div className="auth-footer" style={{ borderTop: 'none', marginTop: '10px' }}>
                    <button
                        onClick={() => sendOTP(userData.email)}
                        disabled={cooldown > 0 || resending}
                        style={{
                            background: 'none',
                            border: 'none',
                            color: cooldown > 0 ? '#6b7280' : '#60a5fa',
                            cursor: cooldown > 0 ? 'not-allowed' : 'pointer',
                            fontWeight: 600
                        }}
                    >
                        {resending ? 'Sending...' : cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend Code'}
                    </button>
                    <p style={{ marginTop: '20px' }}>
                        <a href="/login" onClick={() => { localStorage.clear(); }}>Use a different account</a>
                    </p>
                </div>
            </div>
        </div>
    );
}
