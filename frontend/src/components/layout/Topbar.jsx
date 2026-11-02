import { Bell, ChevronRight, Menu, Moon, Search, Sun } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useTheme } from "../../context/ThemeContext.jsx";
import StatusBadge from "../common/StatusBadge.jsx";
import { navigation } from "../../utils/constants.js";

export default function Topbar({ health, onRefreshHealth, onOpenMobileNav }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [query, setQuery] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const searchInput = useRef(null);
  const current = navigation.find((item) => item.path === location.pathname)
    || (location.pathname.startsWith("/investigations/") ? { label: "Investigation" } : null)
    || { label: "Workspace" };

  useEffect(() => {
    function onShortcut(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchInput.current?.focus();
      }
    }
    window.addEventListener("keydown", onShortcut);
    return () => window.removeEventListener("keydown", onShortcut);
  }, []);

  function submitSearch(event) {
    event.preventDefault();
    const value = query.trim();
    if (value) {
      navigate(`/incidents?search=${encodeURIComponent(value)}`);
      setQuery("");
    }
  }

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button className="icon-button mobile-nav-trigger" aria-label="Open navigation" onClick={onOpenMobileNav}><Menu size={18} /></button>
        <div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14} /><strong>{current.label}</strong></div>
      </div>
      <form className="global-search" onSubmit={submitSearch}>
        <Search size={16} />
        <input ref={searchInput} aria-label="Search incidents" placeholder="Search incidents, services..." value={query} onChange={(event) => setQuery(event.target.value)} />
        <kbd>⌘ K</kbd>
      </form>
      <div className="topbar-actions">
        <button className="health-button" onClick={onRefreshHealth} title={health.error || `Last checked ${health.lastChecked?.toLocaleTimeString() || "—"}`}>
          <StatusBadge status={health.status} label={health.status === "connected" ? "Connected" : health.status === "checking" ? "Checking" : "Disconnected"} />
        </button>
        <div className="notification-wrap">
          <button className={`icon-button ${showNotifications ? "icon-button-selected" : ""}`} aria-label="Notifications" onClick={() => setShowNotifications((shown) => !shown)}>
            <Bell size={17} /><i className="notification-dot" />
          </button>
          {showNotifications && <div className="notification-popover"><strong>Notifications</strong><p>No new notifications. Backend alerts appear here when available.</p></div>}
        </div>
        <button className="icon-button theme-toggle" aria-label="Toggle color theme" onClick={toggleTheme}>
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <div className="topbar-avatar">OP</div>
      </div>
    </header>
  );
}
