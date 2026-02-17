import React, { useState } from 'react';
import '../styles/Auth.css';
import logo from '../assets/ethosh-logo.svg';

export default function ForgotPassword() {
    const [step, setStep] = useState(1); // 1: Email, 2: OTP + New Password
    const [email, setEmail] = useState('');
    const [otp, setOtp] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleRequestOTP = async (e) => {
        e.preventDefault();
        if (!email) {
            setError('Please enter your email');
            return;
        }

        setLoading(true);
        setError('');
        setMessage('');

        try {
            const apiBaseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const response = await fetch(`${apiBaseURL}/api/auth/password-reset-request/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
            });
            const data = await response.json();

            if (response.ok) {
                setMessage('An OTP has been sent to your email.');
                setStep(2);
            } else {
                setError(data.detail || 'Failed to request OTP');
            }
        } catch (err) {
            setError('Network error. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleResetPassword = async (e) => {
        e.preventDefault();
        if (otp.length !== 6) {
            setError('Please enter a 6-digit code');
            return;
        }
        if (newPassword.length < 8) {
            setError('Password must be at least 8 characters');
            return;
        }
        if (newPassword !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }

        setLoading(true);
        setError('');

        try {
            const apiBaseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
            const response = await fetch(`${apiBaseURL}/api/auth/password-reset-confirm/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, otp, new_password: newPassword })
            });
            const data = await response.json();

            if (response.ok) {
                setMessage('Password reset successfully! Redirecting to login...');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
            } else {
                setError(data.detail || 'Failed to reset password');
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
                    <h1>{step === 1 ? 'Forgot Password' : 'Reset Password'}</h1>
                    <p>{step === 1 ? "Enter your email to receive a reset code" : "Enter the code and your new password"}</p>
                </div>

                {step === 1 ? (
                    <form className="auth-form" onSubmit={handleRequestOTP}>
                        {error && <div className="form-error">{error}</div>}
                        {message && <div style={{ color: '#10b981', textAlign: 'center', marginBottom: '10px' }}>{message}</div>}

                        <div className="form-group">
                            <label htmlFor="email">Email Address</label>
                            <input
                                id="email"
                                type="email"
                                className="form-input"
                                placeholder="your@email.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                disabled={loading}
                                autoFocus
                            />
                        </div>

                        <button type="submit" className="form-button" disabled={loading}>
                            {loading ? <div className="spinner"></div> : 'Send Reset Link'}
                        </button>
                    </form>
                ) : (
                    <form className="auth-form" onSubmit={handleResetPassword}>
                        {error && <div className="form-error">{error}</div>}
                        {message && <div style={{ color: '#10b981', textAlign: 'center', marginBottom: '10px' }}>{message}</div>}

                        <div className="form-group">
                            <label htmlFor="otp">6-Digit Code</label>
                            <input
                                id="otp"
                                type="text"
                                className="form-input"
                                placeholder="000000"
                                maxLength="6"
                                value={otp}
                                style={{ textAlign: 'center', fontSize: '20px', letterSpacing: '0.2em' }}
                                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                                disabled={loading}
                                autoFocus
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="newPassword">New Password</label>
                            <input
                                id="newPassword"
                                type="password"
                                className="form-input"
                                placeholder="Min 8 characters"
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                disabled={loading}
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="confirmPassword">Confirm Password</label>
                            <input
                                id="confirmPassword"
                                type="password"
                                className="form-input"
                                placeholder="Confirm new password"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                disabled={loading}
                            />
                        </div>

                        <button type="submit" className="form-button" disabled={loading}>
                            {loading ? <div className="spinner"></div> : 'Reset Password'}
                        </button>
                    </form>
                )}

                <div className="auth-footer">
                    <p><a href="/login">Back to Sign In</a></p>
                </div>
            </div>
        </div>
    );
}
