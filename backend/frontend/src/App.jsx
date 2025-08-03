import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './hooks/useAuth';
import VideoManagementPage from './pages/VideoManagementPage';
import LoginPage from './pages/LoginPage';
import './App.css';

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="App">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/videos" element={<VideoManagementPage />} />
            <Route path="/" element={<Navigate to="/videos" replace />} />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;