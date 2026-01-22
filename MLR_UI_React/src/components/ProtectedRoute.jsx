import React, { useEffect, useState } from 'react';

const ProtectedRoute = ({ children, requiredAuth = true, checkVerification = true }) => {
  const [isValid, setIsValid] = useState(null);
  const [userData, setUserData] = useState(null);

  useEffect(() => {
    const validateToken = () => {
      const token = localStorage.getItem('access_token');
      const userDataStr = localStorage.getItem('user_data');

      if (!token) {
        setIsValid(false);
        return;
      }

      try {
        const data = userDataStr ? JSON.parse(userDataStr) : null;
        setUserData(data);
        setIsValid(true);
      } catch (err) {
        console.error('Invalid user data:', err);
        setIsValid(false);
      }
    };

    validateToken();
  }, []);

  if (isValid === null) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: '#f3f4f6',
        fontSize: '18px',
        color: '#6b7280'
      }}>
        Loading...
      </div>
    );
  }

  if (requiredAuth && !isValid) {
    // Redirect to login if authentication is required but missing
    setTimeout(() => {
      window.location.href = '/login';
    }, 100);
    return null;
  }

  // Check verification if required
  if (requiredAuth && isValid && checkVerification && !userData?.is_email_verified) {
    setTimeout(() => {
      window.location.href = '/verify-email';
    }, 100);
    return null;
  }

  if (!requiredAuth && isValid) {
    // If this is a public route (like login/signup) and user is already authenticated
    // If authenticated but not verified, go to verify-email, else go to dashboard
    setTimeout(() => {
      if (!userData?.is_email_verified) {
        window.location.href = '/verify-email';
      } else {
        window.location.href = '/dashboard';
      }
    }, 100);
    return null;
  }

  return children;
};

export default ProtectedRoute;
