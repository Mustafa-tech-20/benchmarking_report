/**
 * Login Page - RBAC Authentication
 * Industry-standard JWT authentication UI
 */

import React, { useState } from 'react';
import { Loader2, Shield, AlertCircle } from 'lucide-react';
import './Login.css';

interface LoginProps {
  onLoginSuccess: () => void;
}

const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
  const LOGIN_URL = `${API_BASE_URL}/api/auth/login`;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await fetch(LOGIN_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Include cookies
        body: JSON.stringify({ email, password }),
      });

      // Check if response is valid before parsing
      if (!response) {
        throw new Error('No response from server. Please check your connection.');
      }

      // Check for network/CORS errors
      if (!response.ok && response.status === 0) {
        throw new Error('Failed to connect to server. Please try again.');
      }

      // Parse response
      let data;
      try {
        data = await response.json();
      } catch (parseError) {
        throw new Error('Invalid response from server. Please try again.');
      }

      if (!response.ok) {
        throw new Error(data?.detail || 'Login failed');
      }

      // Store user info and token in localStorage
      localStorage.setItem('user', JSON.stringify(data.user));
      localStorage.setItem('access_token', data.access_token);

      // Call success callback
      onLoginSuccess();

    } catch (err: any) {
      console.error('Login error:', err);

      // Better error messages
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        setError('Failed to connect to server. Please ensure the backend is running.');
      } else {
        setError(err.message || 'An error occurred during login. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="login-container">
      <div className="login-background"></div>

      <div className="login-content">
        <div className="login-card">
          {/* Logo and Header */}
          <div className="login-header">
            {/* Logo placeholder - add your organization's logo */}
            <h1 className="login-title">Car Benchmarking Platform</h1>
            <p className="login-subtitle">Sign in to access your agent</p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="login-error">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="login-form">
            <div className="form-group">
              <label htmlFor="email" className="form-label">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="form-input"
                placeholder="you@company.com"
                required
                disabled={isLoading}
              />
            </div>

            <div className="form-group">
              <label htmlFor="password" className="form-label">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="form-input"
                placeholder="Enter your password"
                required
                disabled={isLoading}
              />
            </div>

            <button
              type="submit"
              className="login-button"
              disabled={isLoading || !email || !password}
            >
              {isLoading ? (
                <>
                  <Loader2 className="button-spinner" size={18} />
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <Shield size={18} />
                  <span>Sign In</span>
                </>
              )}
            </button>
          </form>


          {/* Footer */}
          <div className="login-footer">
            <p>End-to-End Encrypted</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
