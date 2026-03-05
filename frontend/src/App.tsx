/**
 * Car Benchmarking AI Agent - Professional Chat Interface
 * Mahindra Color Scheme with Industry-Standard UX
 */

import React, { useState, useEffect, useRef } from 'react';
import { Send, Upload, X, FileText, Loader2, ChevronDown, Car, Settings, BarChart3, Plus, User, Bot } from 'lucide-react';
import { getSessionFromCookies, saveSessionToCookies, clearSessionCookies } from './utils/cookies';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ;
const API_URL = `${API_BASE_URL}/compare`;

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

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [session, setSession] = useState<SessionInfo>({ userId: null, sessionId: null });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<'benchmarking' | 'pcm'>('benchmarking');
  const [showAgentDropdown, setShowAgentDropdown] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load session from cookies on mount
  useEffect(() => {
    const savedSession = getSessionFromCookies();
    if (savedSession.userId && savedSession.sessionId) {
      setSession(savedSession);
      console.log('Loaded session from cookies:', savedSession);
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
    const file = e.target.files?.[0];
    console.log('File selected:', file);
    if (file) {
      if (file.type !== 'application/pdf') {
        alert('Please select a PDF file');
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        alert('File size must be less than 10MB');
        return;
      }
      setSelectedFile(file);
      console.log('File set to state:', file.name);
    }
  };

  const removeFile = () => {
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const sendMessage = async () => {
    if (!input.trim() && !selectedFile) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim() || `[Uploaded: ${selectedFile?.name}]`,
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

    // Store selectedFile in a variable before clearing state
    const fileToUpload = selectedFile;
    console.log('File to upload:', fileToUpload);

    try {
      const formData = new FormData();
      formData.append('query', userMessage.content);

      if (fileToUpload) {
        formData.append('pdf_file', fileToUpload);
        console.log('PDF file added to FormData:', fileToUpload.name);
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
      } else {
        console.log('No file to upload');
      }

      // Build headers with session info (if exists)
      const headers: HeadersInit = {};
      if (session.userId) headers['X-User-Id'] = session.userId;
      if (session.sessionId) headers['X-Session-Id'] = session.sessionId;

      // Log FormData contents
      console.log('FormData entries:');
      for (const [key, value] of formData.entries()) {
        console.log(key, value);
      }

      const response = await fetch(API_URL, {
        method: 'POST',
        headers,
        body: formData,
      });

      console.log('Response status:', response.status);

      const data = await response.json();

      // Save session to cookies on FIRST message only
      if (!session.userId && data.user_id && data.session_id) {
        const newSession = { userId: data.user_id, sessionId: data.session_id };
        setSession(newSession);
        saveSessionToCookies(newSession);
        console.log('Session saved to cookies:', newSession);
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
        content: '❌ Error connecting to the agent. Please try again.',
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && (input.trim() || selectedFile)) {
      e.preventDefault();
      sendMessage();
    }
  };

  const startNewConversation = () => {
    setMessages([]);
    setSession({ userId: null, sessionId: null });
    clearSessionCookies();
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    console.log('Session cleared');
  };

  // Utility functions to extract structured data from response
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

  // Format message text with markdown-style bold
  const formatMessageText = (text: string) => {
    // Split by ** and alternate between normal and bold
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        // Remove ** and make bold
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
          <img
            src="https://www.mahindra.com//sites/default/files/2025-07/mahindra-red-logo.webp"
            alt="Mahindra"
            className="nav-logo"
          />
        </div>

        <div className="nav-center">
          <div className="nav-dropdown">
            <button
              className="dropdown-btn"
              onClick={() => setShowAgentDropdown(!showAgentDropdown)}
            >
              <Car size={16} />
              <span>{selectedAgent === 'benchmarking' ? 'Benchmarking Agent' : 'PCM Agent'}</span>
              <ChevronDown size={16} />
            </button>
            {showAgentDropdown && (
              <div className="dropdown-menu">
                <button
                  className="dropdown-item"
                  onClick={() => {
                    setSelectedAgent('benchmarking');
                    setShowAgentDropdown(false);
                    startNewConversation();
                  }}
                >
                  <Car size={16} />
                  <span>Benchmarking Agent</span>
                </button>
                <button
                  className="dropdown-item"
                  onClick={() => {
                    setSelectedAgent('pcm');
                    setShowAgentDropdown(false);
                    startNewConversation();
                  }}
                >
                  <Settings size={16} />
                  <span>PCM Agent</span>
                </button>
              </div>
            )}
          </div>

          <button className="nav-btn">
            <BarChart3 size={16} />
            <span>Reports</span>
          </button>

          <button className="nav-btn">
            <FileText size={16} />
            <span>History</span>
          </button>
        </div>

        <div className="nav-right">
          <div className="user-profile">
            <div className="user-avatar">
              <User size={18} />
            </div>
            <div className="user-info">
              <div className="user-name">Mahindra User</div>
              <div className="user-credits">Active Session</div>
            </div>
          </div>

          <button className="create-btn" onClick={startNewConversation}>
            <Plus size={18} />
            <span>New Chat</span>
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="main-container">
        {/* Chat Container */}
        <div className="chat-container" ref={chatContainerRef}>
        {messages.length === 0 ? (
          <div className="welcome-screen">
            <div className="welcome-content">
              <h2>Car Benchmarking Platform</h2>
              <p className="welcome-description">
                Compare prototype and production vehicles using internal datasets and curated external intelligence.
              </p>
            </div>

            <div className="example-queries">
              <div className="examples-label">
                <span>Benchmark Templates</span>
                <div className="label-line"></div>
              </div>
              <div className="query-grid">
                <button className="query-card" onClick={() => setInput('Compare Mahindra Thar and Hyundai Creta')}>
                  <div className="card-icon-wrapper">
                    <Car size={24} strokeWidth={1.5} />
                  </div>
                  <div className="card-content">
                    <div className="card-title">Market Comparison</div>
                    <div className="card-description">Mahindra Thar vs Hyundai Creta</div>
                  </div>
                </button>
                <button className="query-card" onClick={() => setInput('CODE:PROTO1, Hyundai Creta')}>
                  <div className="card-icon-wrapper">
                    <Settings size={24} strokeWidth={1.5} />
                  </div>
                  <div className="card-content">
                    <div className="card-title">Prototype Analysis</div>
                    <div className="card-description">Compare internal prototype with competitor</div>
                  </div>
                </button>
                <button className="query-card" onClick={() => setInput('Summarize this PDF')}>
                  <div className="card-icon-wrapper">
                    <BarChart3 size={24} strokeWidth={1.5} />
                  </div>
                  <div className="card-content">
                    <div className="card-title">Document Analysis</div>
                    <div className="card-description">Extract specs from uploaded PDF</div>
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
                      <span>Analyzing...</span>
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
        <button
          className="scroll-bottom-btn"
          onClick={scrollToBottom}
        >
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
            accept="application/pdf"
            style={{ display: 'none' }}
          />

          {selectedFile && (
            <div className="file-badge">
              <FileText size={14} />
              <span>{selectedFile.name}</span>
              <button onClick={removeFile} className="file-remove">
                <X size={12} />
              </button>
            </div>
          )}

          <div className="chatgpt-input-box">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="chatgpt-icon-btn"
              disabled={isLoading}
            >
              <Plus size={20} />
            </button>

            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything"
              className="chatgpt-textarea"
              disabled={isLoading}
              rows={1}
            />

            <button
              onClick={sendMessage}
              disabled={isLoading || (!input.trim() && !selectedFile)}
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
              accept="application/pdf"
              style={{ display: 'none' }}
            />

            {selectedFile && (
              <div className="file-badge">
                <FileText size={14} />
                <span>{selectedFile.name}</span>
                <button onClick={removeFile} className="file-remove">
                  <X size={12} />
                </button>
              </div>
            )}

            <div className="chatgpt-input-box">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="chatgpt-icon-btn"
                disabled={isLoading}
              >
                <Plus size={20} />
              </button>

              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything"
                className="chatgpt-textarea"
                disabled={isLoading}
                rows={1}
              />

              <button
                onClick={sendMessage}
                disabled={isLoading || (!input.trim() && !selectedFile)}
                className="chatgpt-send-btn"
              >
                {isLoading ? <Loader2 className="spinner" size={18} /> : <Send size={18} />}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
