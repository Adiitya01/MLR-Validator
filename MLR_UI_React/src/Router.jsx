import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import App from './App';
import SignupForm from './components/SignupForm';
import LoginForm from './components/LoginForm';
import VerifyOTP from './components/VerifyOTP';
import ForgotPassword from './components/ForgotPassword';
import ProtectedRoute from './components/ProtectedRoute';

const Router = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* Protected Dashboard Route */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute requiredAuth={true}>
              <App />
            </ProtectedRoute>
          }
        />

        {/* Public Auth Routes */}
        <Route
          path="/signup"
          element={
            <ProtectedRoute requiredAuth={false}>
              <SignupForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/login"
          element={
            <ProtectedRoute requiredAuth={false}>
              <LoginForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="/verify-email"
          element={
            <ProtectedRoute requiredAuth={true} checkVerification={false}>
              <VerifyOTP />
            </ProtectedRoute>
          }
        />
        <Route
          path="/forgot-password"
          element={
            <ProtectedRoute requiredAuth={false}>
              <ForgotPassword />
            </ProtectedRoute>
          }
        />

        {/* Default Redirects */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default Router;
