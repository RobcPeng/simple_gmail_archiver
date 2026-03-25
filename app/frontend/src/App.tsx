import { useEffect, useState } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Search from './pages/Search';
import ReviewQueue from './pages/ReviewQueue';
import Schedules from './pages/Schedules';
import Settings from './pages/Settings';
import Login from './pages/Login';
import { api, AuthStatus } from './api';
import './App.css';

function App() {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = () => {
    api.getAuthStatus()
      .then((status) => {
        setAuth(status);
        setLoading(false);
      })
      .catch(() => {
        // API not reachable — show login anyway
        setAuth({ authenticated: false });
        setLoading(false);
      });
  };

  useEffect(checkAuth, []);

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', background: 'var(--bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--text-secondary)', fontSize: 13,
      }}>
        Loading...
      </div>
    );
  }

  if (!auth?.authenticated) {
    return <Login />;
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>GmailVault</h1>
          <span>{auth.email || 'Email Archive'}</span>
        </div>
        <nav className="sidebar-nav">
          <NavLink to="/" end>
            <span className="nav-icon">&#9632;</span> Dashboard
          </NavLink>
          <NavLink to="/search">
            <span className="nav-icon">&#8981;</span> Search
          </NavLink>
          <NavLink to="/review">
            <span className="nav-icon">&#9998;</span> Review Queue
          </NavLink>
          <NavLink to="/schedules">
            <span className="nav-icon">&#9201;</span> Schedules
          </NavLink>
          <NavLink to="/settings">
            <span className="nav-icon">&#9881;</span> Settings
          </NavLink>
        </nav>
      </aside>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/search" element={<Search />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/schedules" element={<Schedules />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
