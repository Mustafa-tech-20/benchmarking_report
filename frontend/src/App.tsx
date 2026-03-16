/**
 * Car Benchmarking AI Agent - Professional Chat Interface with RBAC
 * Mahindra Color Scheme with Industry-Standard UX
 */

import React, { useState, useEffect, useRef } from 'react';
import { Send, X, FileText, Loader2, ChevronDown, Car, Settings, BarChart3, Plus, Bot, LogOut, History, MessageSquare, Trash2 } from 'lucide-react';
import { getSessionFromCookies, saveSessionToCookies, clearSessionCookies } from './utils/cookies';
import Login from './Login';
import './App.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const API_URL = `${API_BASE_URL}/api/compare`;
const LOGOUT_URL = `${API_BASE_URL}/api/auth/logout`;
const CONVERSATIONS_URL = `${API_BASE_URL}/api/conversations`;

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
  conversationId: string | null;
}

interface UserInfo {
  email: string;
  role: string;
  full_name: string | null;
  is_active: boolean;
}

interface ConversationListItem {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface ConversationDetail {
  conversation_id: string;
  user_email: string;
  title: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
  user_id?: string | null;
  session_id?: string | null;
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [session, setSession] = useState<SessionInfo>({ userId: null, sessionId: null, conversationId: null });
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(false);
  const [showUserDropdown, setShowUserDropdown] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const userDropdownRef = useRef<HTMLDivElement>(null);

  // Check authentication status on mount
  useEffect(() => {
    const storedUser = localStorage.getItem('user');
    const accessToken = localStorage.getItem('access_token');

    if (storedUser && accessToken) {
      try {
        const parsedUser = JSON.parse(storedUser);
        setUser(parsedUser);
        setIsAuthenticated(true);
      } catch (error) {
        console.error('Failed to parse user data:', error);
        handleLogout();
      }
    }
  }, []);

  // Load session from cookies on mount
  useEffect(() => {
    if (isAuthenticated) {
      const savedSession = getSessionFromCookies();
      if (savedSession.userId && savedSession.sessionId) {
        setSession(savedSession);
        console.log('Loaded session from cookies:', savedSession);
      }
      // Load conversation history
      fetchConversations();
    }
  }, [isAuthenticated]);

  // Fetch conversation history
  const fetchConversations = async () => {
    try {
      setLoadingConversations(true);
      const response = await fetch(CONVERSATIONS_URL, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        setConversations(data);
      }
    } catch (error) {
      console.error('Error fetching conversations:', error);
    } finally {
      setLoadingConversations(false);
    }
  };

  // Load a specific conversation
  const loadConversation = async (conversationId: string) => {
    try {
      const response = await fetch(`${CONVERSATIONS_URL}/${conversationId}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        credentials: 'include',
      });

      if (response.ok) {
        const conversation: ConversationDetail = await response.json();

        // Convert conversation messages to Message format
        // Map snake_case from backend to camelCase for frontend
        const loadedMessages: Message[] = conversation.messages.map((msg: any, index) => ({
          id: `${conversationId}-${index}`,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          timestamp: new Date(msg.timestamp),
          reportUrl: msg.report_url || msg.reportUrl,
          carsCompared: msg.cars_compared || msg.carsCompared,
          timeTaken: msg.time_taken || msg.timeTaken,
        }));

        setMessages(loadedMessages);
        setSession({
          userId: conversation.user_id || null,
          sessionId: conversation.session_id || null,
          conversationId: conversation.conversation_id,
        });
        setShowHistory(false);
      }
    } catch (error) {
      console.error('Error loading conversation:', error);
    }
  };

  // Delete a conversation
  const deleteConversation = async (conversationId: string, event: React.MouseEvent) => {
    event.stopPropagation();

    if (!confirm('Are you sure you want to delete this conversation?')) {
      return;
    }

    try {
      const response = await fetch(`${CONVERSATIONS_URL}/${conversationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        credentials: 'include',
      });

      if (response.ok) {
        // Refresh conversations list
        fetchConversations();

        // If the deleted conversation is currently loaded, clear it
        if (session.conversationId === conversationId) {
          startNewConversation();
        }
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
    }
  };

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

  // Handle click outside user dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userDropdownRef.current && !userDropdownRef.current.contains(event.target as Node)) {
        setShowUserDropdown(false);
      }
    };

    if (showUserDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showUserDropdown]);

  const handleLoginSuccess = () => {
    const storedUser = localStorage.getItem('user');
    if (storedUser) {
      const parsedUser = JSON.parse(storedUser);
      setUser(parsedUser);
      setIsAuthenticated(true);
    }
  };

  const handleLogout = async () => {
    setShowUserDropdown(false);
    try {
      await fetch(LOGOUT_URL, {
        method: 'POST',
        credentials: 'include',
      });
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      localStorage.removeItem('user');
      localStorage.removeItem('access_token');
      clearSessionCookies();
      setUser(null);
      setIsAuthenticated(false);
      setMessages([]);
      setSession({ userId: null, sessionId: null, conversationId: null });
      setConversations([]);
      setShowHistory(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const validFiles: File[] = [];
    let totalSize = selectedFiles.reduce((sum, f) => sum + f.size, 0);

    for (const file of files) {
      if (file.type !== 'application/pdf') {
        alert(`${file.name} is not a PDF file`);
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

      // Build headers with session info and authentication
      const headers: HeadersInit = {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
      };
      if (session.userId) headers['X-User-Id'] = session.userId;
      if (session.sessionId) headers['X-Session-Id'] = session.sessionId;
      if (session.conversationId) headers['X-Conversation-Id'] = session.conversationId;

      const response = await fetch(API_URL, {
        method: 'POST',
        headers,
        body: formData,
        credentials: 'include', // Include cookies
      });

      // Check for authentication errors
      if (response.status === 401 || response.status === 403) {
        handleLogout();
        setMessages(prev => prev.filter(m => m.id !== loadingId));
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: '🔒 Session expired. Please log in again.',
          timestamp: new Date(),
        }]);
        return;
      }

      const data = await response.json();

      // Check for error responses from backend
      if (!response.ok) {
        setMessages(prev => prev.filter(m => m.id !== loadingId));
        const errorMessage = data.detail || data.error || data.message || 'An error occurred';

        // Check if it's a session not found error
        if (errorMessage.toLowerCase().includes('session not found') ||
            errorMessage.toLowerCase().includes('session expired')) {
          // Clear the invalid session and prompt user to start fresh
          clearSessionCookies();
          setSession({ userId: null, sessionId: null, conversationId: null });
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'assistant',
            content: '⚠️ Your previous session has expired. Please start a new conversation.',
            timestamp: new Date(),
          }]);
        } else {
          setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'assistant',
            content: `⚠️ ${errorMessage}`,
            timestamp: new Date(),
          }]);
        }
        return;
      }

      // Update session with IDs from response
      const newSession = {
        userId: data.user_id || session.userId,
        sessionId: data.session_id || session.sessionId,
        conversationId: data.conversation_id || session.conversationId,
      };

      if (newSession.userId && newSession.sessionId) {
        setSession(newSession);
        saveSessionToCookies(newSession);
      }

      // Refresh conversation list if we have a new conversation
      if (data.conversation_id && data.conversation_id !== session.conversationId) {
        fetchConversations();
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
    if (e.key === 'Enter' && !e.shiftKey && (input.trim() || selectedFiles.length > 0)) {
      e.preventDefault();
      sendMessage();
    }
  };

  const startNewConversation = () => {
    setMessages([]);
    setSession({ userId: null, sessionId: null, conversationId: null });
    clearSessionCookies();
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setShowHistory(false);
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

  const getAgentName = (role: string): string => {
    const roleMap: Record<string, string> = {
      'VB': 'Vehicle Benchmarking Agent',
      'PP': 'Product Planning Agent',
      'VD': 'Vehicle Development Agent',
    };
    return roleMap[role] || 'Benchmarking Agent';
  };

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

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

        <div className="nav-right">
          <div className="nav-agent-display">
            <Car size={16} />
            <span>{getAgentName(user?.role || '')}</span>
          </div>

          <button className="nav-btn" onClick={startNewConversation}>
            <Plus size={18} />
            <span>New Chat</span>
          </button>

          <button className="nav-btn" onClick={() => setShowHistory(!showHistory)}>
            <History size={18} />
            <span>History</span>
          </button>

          <div className="user-profile-wrapper" ref={userDropdownRef}>
            <div
              className="user-profile-dropdown"
              onClick={() => setShowUserDropdown(!showUserDropdown)}
            >
              <div className="user-avatar-circle">
                {(user?.full_name || user?.email || 'U').substring(0, 2).toUpperCase()}
              </div>
              <div className="user-info">
                <div className="user-name">{user?.full_name || user?.email}</div>
                <div className="user-credits">{user?.role} Role</div>
              </div>
              <button className="user-dropdown-btn">
                <ChevronDown size={16} />
              </button>
            </div>

            {showUserDropdown && (
              <div className="user-dropdown-menu">
                <button className="user-dropdown-item" onClick={handleLogout}>
                  <LogOut size={16} />
                  <span>Logout</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* History Sidebar */}
      {showHistory && (
        <>
          <div className="history-overlay" onClick={() => setShowHistory(false)} />
          <div className="history-sidebar">
            <div className="history-header">
              <h3>
                <MessageSquare size={20} />
                Conversation History
              </h3>
              <button className="close-history" onClick={() => setShowHistory(false)}>
                <X size={20} />
              </button>
            </div>

            <div className="history-content">
              {loadingConversations ? (
                <div className="history-loading">
                  <Loader2 className="spinner" size={24} />
                  <p>Loading conversations...</p>
                </div>
              ) : conversations.length === 0 ? (
                <div className="history-empty">
                  <MessageSquare size={48} opacity={0.3} />
                  <p>No conversations yet</p>
                  <span>Start a new chat to begin</span>
                </div>
              ) : (
                <div className="conversation-list">
                  {conversations.map((conv) => (
                    <div
                      key={conv.conversation_id}
                      className={`conversation-item ${session.conversationId === conv.conversation_id ? 'active' : ''}`}
                      onClick={() => loadConversation(conv.conversation_id)}
                    >
                      <div className="conversation-main">
                        <div className="conversation-title">{conv.title}</div>
                        <div className="conversation-meta">
                          {conv.message_count} messages • {new Date(conv.updated_at).toLocaleDateString()}
                        </div>
                      </div>
                      <button
                        className="delete-conversation"
                        onClick={(e) => deleteConversation(conv.conversation_id, e)}
                        title="Delete conversation"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Main Container */}
      <div className="main-container">
        <div className="chat-container" ref={chatContainerRef}>
        {messages.length === 0 ? (
          <div className="welcome-screen">
            <div className="welcome-content">
              <h2>Car Benchmarking Platform</h2>
              <p className="welcome-description">
                Compare prototype and production vehicles using internal datasets and curated external intelligence.
                You're using the <strong>{getAgentName(user?.role || '')}</strong>.
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
            accept="application/pdf"
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
              title={selectedFiles.length >= 10 ? 'Maximum 10 files' : 'Add PDFs'}
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
              accept="application/pdf"
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
                title={selectedFiles.length >= 10 ? 'Maximum 10 files' : 'Add PDFs'}
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
                disabled={isLoading || (!input.trim() && selectedFiles.length === 0)}
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
