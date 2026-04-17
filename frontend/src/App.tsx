/**
 * Vehicle Development Agent - Chat Interface
 * Direct access without authentication
 */

import React, { useState, useEffect, useRef } from 'react';
import { Send, X, FileText, Loader2, ChevronDown, Car, Settings, BarChart3, Plus, Bot, Sun, Moon } from 'lucide-react';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const API_URL = `${API_BASE_URL}/api/compare`;

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
  reportUrl?: string;
  carsCompared?: string;
  timeTaken?: string;
}

interface SessionInfo {
  userId: string | null;
  sessionId: string | null;
}

interface Toast {
  id: string;
  message: string;
  type: 'error' | 'success' | 'info';
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [session, setSession] = useState<SessionInfo>({ userId: null, sessionId: null });
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [isDarkMode, setIsDarkMode] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Toast notification functions
  const showToast = (message: string, type: 'error' | 'success' | 'info' = 'info') => {
    const id = Date.now().toString();
    const newToast: Toast = { id, message, type };
    setToasts(prev => [...prev, newToast]);

    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  // Theme toggle effect
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.remove('light-theme');
    } else {
      document.documentElement.classList.add('light-theme');
    }
  }, [isDarkMode]);

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
  };

  // Load session from localStorage on mount
  useEffect(() => {
    const savedUserId = localStorage.getItem('vd_user_id');
    const savedSessionId = localStorage.getItem('vd_session_id');
    if (savedUserId && savedSessionId) {
      setSession({ userId: savedUserId, sessionId: savedSessionId });
    }
  }, []);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Handle scroll for "scroll to bottom" button
  useEffect(() => {
    const handleScroll = () => {
      if (chatContainerRef.current) {
        const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
        setShowScrollButton(scrollHeight - scrollTop - clientHeight > 100);
      }
    };

    const container = chatContainerRef.current;
    container?.addEventListener('scroll', handleScroll);
    return () => container?.removeEventListener('scroll', handleScroll);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const validFiles: File[] = [];
    let totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);

    const SUPPORTED_TYPES = [
      'application/pdf',
      'text/csv',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ];
    const SUPPORTED_EXTENSIONS = ['.pdf', '.csv', '.xls', '.xlsx'];

    for (const file of files) {
      const fileExt = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
      const isValidType = SUPPORTED_TYPES.includes(file.type) || SUPPORTED_EXTENSIONS.includes(fileExt);

      if (!isValidType) {
        alert(`${file.name} is not a supported file type. Supported: PDF, CSV, Excel`);
        continue;
      }
      if (file.size > 10 * 1024 * 1024) {
        alert(`${file.name} exceeds 10MB limit`);
        continue;
      }
      if (selectedFiles.length + validFiles.length >= 10) {
        alert('Maximum 10 files allowed');
        break;
      }
      totalSize += file.size;
      if (totalSize > 30 * 1024 * 1024) {
        alert('Total file size exceeds 30MB limit');
        break;
      }
      validFiles.push(file);
    }

    if (validFiles.length > 0) {
      setSelectedFiles(prev => [...prev, ...validFiles]);
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const clearAllFiles = () => {
    setSelectedFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const sendMessage = async () => {
    if (!input.trim() && selectedFiles.length === 0) return;

    const fileNames = selectedFiles.map(f => f.name).join(', ');
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim() || `[Uploaded: ${fileNames}]`,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');

    // Add loading message
    const loadingId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, {
      id: loadingId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isLoading: true,
    }]);

    setIsLoading(true);

    const filesToUpload = [...selectedFiles];

    try {
      const formData = new FormData();
      formData.append('query', userMessage.content);

      if (filesToUpload.length > 0) {
        filesToUpload.forEach(file => {
          formData.append('pdf_files', file);
        });
        setSelectedFiles([]);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }

      // Build headers with session info
      const headers: HeadersInit = {};
      if (session.userId) headers['X-User-Id'] = session.userId;
      if (session.sessionId) headers['X-Session-Id'] = session.sessionId;

      const response = await fetch(API_URL, {
        method: 'POST',
        headers,
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        setMessages(prev => prev.filter(m => m.id !== loadingId));
        const errorMessage = data.detail || data.error || data.message || 'An error occurred';

        if (errorMessage.toLowerCase().includes('session not found') ||
            errorMessage.toLowerCase().includes('session expired')) {
          localStorage.removeItem('vd_user_id');
          localStorage.removeItem('vd_session_id');
          setSession({ userId: null, sessionId: null });
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'assistant',
            content: 'Your session has expired. Please start a new conversation.',
            timestamp: new Date(),
          }]);
        } else {
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'assistant',
            content: `Error: ${errorMessage}`,
            timestamp: new Date(),
          }]);
        }
        return;
      }

      // Update session with IDs from response
      const newSession = {
        userId: data.user_id || session.userId,
        sessionId: data.session_id || session.sessionId,
      };

      if (newSession.userId && newSession.sessionId) {
        setSession(newSession);
        localStorage.setItem('vd_user_id', newSession.userId);
        localStorage.setItem('vd_session_id', newSession.sessionId);
      }

      // Remove loading message and add actual response
      setMessages(prev => prev.filter(m => m.id !== loadingId));

      const assistantMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: data.response || data.message || 'No response received',
        timestamp: new Date(),
        reportUrl: extractReportUrl(data.response),
        carsCompared: extractCarsCompared(data.response),
        timeTaken: extractTimeTaken(data.response),
      };

      setMessages(prev => [...prev, assistantMessage]);

    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => prev.filter(m => m.id !== loadingId));
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Error connecting to the agent. Please try again.',
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && (input.trim() || selectedFiles.length > 0)) {
      e.preventDefault();
      sendMessage();
    }
  };

  const startNewConversation = () => {
    setMessages([]);
    setSession({ userId: null, sessionId: null });
    localStorage.removeItem('vd_user_id');
    localStorage.removeItem('vd_session_id');
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Utility functions
  const extractReportUrl = (text: string): string | undefined => {
    const match = text?.match(/https:\/\/storage\.googleapis\.com\/[^\s]+/);
    return match ? match[0] : undefined;
  };

  const extractCarsCompared = (text: string): string | undefined => {
    const match = text?.match(/Compared:\s*(.+?)(?:\n|$)/);
    return match ? match[1].trim() : undefined;
  };

  const extractTimeTaken = (text: string): string | undefined => {
    const match = text?.match(/Time:\s*([\d.]+)\s*seconds?/);
    return match ? `${match[1]}s` : undefined;
  };

  const formatMessageText = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        const boldText = part.slice(2, -2);
        return <strong key={index}>{boldText}</strong>;
      }
      return part;
    });
  };

  return (
    <div className="app">
      {/* Top Navigation */}
      <header className="top-nav">
        <div className="nav-left">
          {/* Logo placeholder */}
        </div>

        <div className="nav-right">
          <div className="nav-agent-display">
            <Car size={14} />
            <span>Vehicle Development Agent</span>
          </div>

          <button className="nav-btn" onClick={startNewConversation}>
            <Plus size={16} />
            <span>New Chat</span>
          </button>

          <button className="theme-toggle" onClick={toggleTheme} title={isDarkMode ? 'Light mode' : 'Dark mode'}>
            {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="main-container">
        <div className="chat-container" ref={chatContainerRef}>
        {messages.length === 0 ? (
          <div className="welcome-screen">
            <div className="welcome-content">
              <h2>Vehicle Development Agent</h2>
              <p className="welcome-description">
                AI-powered vehicle development analysis and comparison.
              </p>
            </div>

            <div className="example-queries">
              <div className="examples-label">
                <span>Templates</span>
                <div className="label-line"></div>
              </div>
              <div className="query-grid">
                <button className="query-card" onClick={() => setInput('Compare [Car Name 1] and [Car Name 2]')}>
                  <div className="card-icon-wrapper">
                    <Car size={18} strokeWidth={1.5} />
                  </div>
                  <div className="card-content">
                    <div className="card-title">Vehicle Comparison</div>
                    <div className="card-description">Enter car names to compare</div>
                  </div>
                </button>
                <button className="query-card" onClick={() => setInput('CODE:PROTO1, Hyundai Creta')}>
                  <div className="card-icon-wrapper">
                    <Settings size={18} strokeWidth={1.5} />
                  </div>
                  <div className="card-content">
                    <div className="card-title">Prototype Analysis (RAG)</div>
                    <div className="card-description">Fetch internal CODE: car specs from RAG corpus</div>
                  </div>
                </button>
                <button className="query-card" onClick={() => setInput('compare CODE:PROTO1 from uploaded PDF/Excel with ')}>
                  <div className="card-icon-wrapper">
                    <FileText size={18} strokeWidth={1.5} />
                  </div>
                  <div className="card-content">
                    <div className="card-title">Prototype Analysis (PDF/Excel)</div>
                    <div className="card-description">Upload spec PDF/Excel for comparison</div>
                  </div>
                </button>
                <button className="query-card" onClick={() => setInput('Summarize this PDF/Excel')}>
                  <div className="card-icon-wrapper">
                    <BarChart3 size={18} strokeWidth={1.5} />
                  </div>
                  <div className="card-content">
                    <div className="card-title">Document Analysis</div>
                    <div className="card-description">Summarize uploaded PDF/Excel</div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="messages-list">
            {messages.map((message) => (
              <div key={message.id} className={`message message-${message.role}`}>
                <div className="message-avatar">
                  {message.role === 'user' ? (
                    <div className="avatar-user">You</div>
                  ) : (
                    <div className="avatar-ai">
                      <Bot size={16} />
                    </div>
                  )}
                </div>

                <div className="message-content">
                  {message.isLoading ? (
                    <div className="loading-indicator">
                      <Loader2 className="spinner" />
                      <span>Analyzing</span>
                    </div>
                  ) : (
                    <>
                      {message.reportUrl ? (
                        <div className="report-card">
                          <div className="report-header">
                            <span>Comparison Complete!</span>
                          </div>

                          {message.carsCompared && (
                            <div className="report-detail">
                              <strong>Cars:</strong> {message.carsCompared}
                            </div>
                          )}

                          {message.timeTaken && (
                            <div className="report-detail">
                              <strong>Time:</strong> {message.timeTaken}
                            </div>
                          )}

                          <a
                            href={message.reportUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="view-report-btn"
                          >
                            <FileText size={18} />
                            View Detailed Report
                          </a>
                        </div>
                      ) : (
                        <div className="message-text">{formatMessageText(message.content)}</div>
                      )}

                      <div className="message-time">
                        {message.timestamp.toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Scroll to Bottom Button */}
      {showScrollButton && (
        <button className="scroll-bottom-btn" onClick={scrollToBottom}>
          <ChevronDown size={20} />
        </button>
      )}

      {/* Chat Input */}
      {messages.length > 0 && (
        <div className="chatgpt-input-container">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".pdf,.csv,.xls,.xlsx,application/pdf,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            multiple
            style={{ display: 'none' }}
          />

          {selectedFiles.length > 0 && (
            <div className="files-container">
              {selectedFiles.map((file, index) => (
                <div key={index} className="file-badge">
                  <FileText size={14} />
                  <span>{file.name}</span>
                  <button onClick={() => removeFile(index)} className="file-remove">
                    <X size={12} />
                  </button>
                </div>
              ))}
              {selectedFiles.length > 1 && (
                <button onClick={clearAllFiles} className="clear-all-btn">
                  Clear all
                </button>
              )}
            </div>
          )}

          <div className="chatgpt-input-box">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="chatgpt-icon-btn"
              disabled={isLoading || selectedFiles.length >= 10}
              title={selectedFiles.length >= 10 ? 'Maximum 10 files' : 'Add PDF/Excel'}
            >
              <Plus size={20} />
            </button>

            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter your query..."
              className="chatgpt-textarea"
              disabled={isLoading}
              rows={1}
            />

            <button
              onClick={sendMessage}
              disabled={isLoading || (!input.trim() && selectedFiles.length === 0)}
              className="chatgpt-send-btn"
            >
              {isLoading ? <Loader2 className="spinner" size={18} /> : <Send size={18} />}
            </button>
          </div>
        </div>
      )}

      {/* Welcome Input */}
      {messages.length === 0 && (
          <div className="welcome-input-area">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept=".pdf,.csv,.xls,.xlsx,application/pdf,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              multiple
              style={{ display: 'none' }}
            />

            {selectedFiles.length > 0 && (
              <div className="files-container">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="file-badge">
                    <FileText size={14} />
                    <span>{file.name}</span>
                    <button onClick={() => removeFile(index)} className="file-remove">
                      <X size={12} />
                    </button>
                  </div>
                ))}
                {selectedFiles.length > 1 && (
                  <button onClick={clearAllFiles} className="clear-all-btn">
                    Clear all
                  </button>
                )}
              </div>
            )}

            <div className="chatgpt-input-box">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="chatgpt-icon-btn"
                disabled={isLoading || selectedFiles.length >= 10}
                title={selectedFiles.length >= 10 ? 'Maximum 10 files' : 'Add PDF/Excel'}
              >
                <Plus size={20} />
              </button>

              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Enter your query..."
                className="chatgpt-textarea"
                disabled={isLoading}
                rows={1}
              />

              <button
                onClick={sendMessage}
                disabled={isLoading || (!input.trim() && selectedFiles.length === 0)}
                className="chatgpt-send-btn"
              >
                {isLoading ? <Loader2 className="spinner" size={18} /> : <Send size={18} />}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Toast Notifications */}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.type}`}>
            <span>{toast.message}</span>
            <button className="toast-close" onClick={() => removeToast(toast.id)}>
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
