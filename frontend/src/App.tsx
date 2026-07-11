import { BrowserRouter, Routes, Route, NavLink } from 'react-router';
import ProjectPage from '@/pages/ProjectPage';
import AnalysisPage from '@/pages/AnalysisPage';
import ChatPage from '@/pages/ChatPage';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <nav className="navbar">
        <div className="navbar-brand">Code Analysis</div>
        <div className="navbar-links">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Projects
          </NavLink>
          <NavLink to="/analysis" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            Analysis
          </NavLink>
          <NavLink to="/chat" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
            AI Chat
          </NavLink>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<ProjectPage />} />
        <Route path="/analysis" element={<AnalysisPage />} />
        <Route path="/chat" element={<ChatPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
