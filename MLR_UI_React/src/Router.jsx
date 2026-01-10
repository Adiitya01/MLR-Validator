import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import App from './App';
import SignupForm from './components/SignupForm';
import LoginForm from './components/LoginForm';

const Router = () => {
  const isAuthenticated = () => {
    return localStorage.getItem('access_token') !== null;
  };

  return (
    <BrowserRouter>
      <Routes>
        {/* Public Routes - Redirect to dashboard if already authenticated */}
        <Route 
          path="/signup" 
          element={
            isAuthenticated() ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <SignupForm />
            )
          } 
        />
        <Route 
          path="/login" 
          element={
            isAuthenticated() ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <LoginForm />
            )
          } 
        />

        {/* Protected Routes - Require authentication */}
        <Route 
          path="/dashboard" 
          element={
            isAuthenticated() ? (
              <App />
            ) : (
              <Navigate to="/login" replace />
            )
          } 
        />
        
        {/* Default route */}
        <Route 
          path="/" 
          element={
            isAuthenticated() ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <Navigate to="/login" replace />
            )
          } 
        />

        {/* Catch-all route */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default Router;
