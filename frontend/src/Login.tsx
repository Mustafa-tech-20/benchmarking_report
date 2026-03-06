/**
 * Login Page - Mahindra RBAC Authentication
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

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Login failed');
      }

      // Store user info and token in localStorage
      localStorage.setItem('user', JSON.stringify(data.user));
      localStorage.setItem('access_token', data.access_token);

      // Call success callback
      onLoginSuccess();

    } catch (err: any) {
      setError(err.message || 'An error occurred during login');
    } finally {
      setIsLoading(false);
    }
  };

  const fillTestCredentials = (role: 'VB' | 'PP' | 'VD') => {
    const credentials = {
      VB: { email: 'vb@mahindra.com', password: 'vb123' },
      PP: { email: 'pp@mahindra.com', password: 'pp123' },
      VD: { email: 'vd@mahindra.com', password: 'vd123' },
    };
    setEmail(credentials[role].email);
    setPassword(credentials[role].password);
    setError('');
  };

  return (
    <div className="login-container">
      <div className="login-background"></div>

      <div className="login-content">
        <div className="login-card">
          {/* Logo and Header */}
          <div className="login-header">
            <img
              src="https://www.mahindra.com//sites/default/files/2025-07/mahindra-red-logo.webp"
              alt="Mahindra"
              className="login-logo"
            />
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
                placeholder="you@mahindra.com"
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

          {/* Test Credentials */}
          <div className="test-credentials">
            <div className="divider">
              <span>Test Credentials</span>
            </div>

            <div className="role-badges">
              <button
                type="button"
                className="role-badge"
                onClick={() => fillTestCredentials('VB')}
                disabled={isLoading}
              >
                <div className="role-badge-content">
                  <div className="role-badge-name">VB</div>
                  <div className="role-badge-desc">Vehicle Benchmarking</div>
                </div>
              </button>

              <button
                type="button"
                className="role-badge"
                onClick={() => fillTestCredentials('PP')}
                disabled={isLoading}
              >
                <div className="role-badge-content">
                  <div className="role-badge-name">PP</div>
                  <div className="role-badge-desc">Product Planning</div>
                </div>
              </button>

              <button
                type="button"
                className="role-badge"
                onClick={() => fillTestCredentials('VD')}
                disabled={isLoading}
              >
                <div className="role-badge-content">
                  <div className="role-badge-name">VD</div>
                  <div className="role-badge-desc">Vehicle Development</div>
                </div>
              </button>
            </div>
          </div>

          {/* Footer */}
          <div className="login-footer">
            <p>Secure authentication with industry-standard JWT</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
