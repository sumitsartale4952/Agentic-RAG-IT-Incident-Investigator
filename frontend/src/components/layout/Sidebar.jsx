import { Activity, ChevronLeft, Command, Menu } from "lucide-react";
import { NavLink } from "react-router-dom";
import { navigation } from "../../utils/constants.js";

export default function Sidebar({ collapsed, onToggle, mobileOpen, onNavigate }) {
  return (
    <>
      {mobileOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={onNavigate} />}
      <aside className={`sidebar ${collapsed ? "sidebar-collapsed" : ""} ${mobileOpen ? "sidebar-mobile-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark"><Activity size={19} strokeWidth={2.2} /></div>
          {!collapsed && <div className="brand-copy"><strong>sentinel</strong><span>INCIDENT INTELLIGENCE</span></div>}
          <button className="icon-button sidebar-collapse" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={onToggle}>
            {collapsed ? <Menu size={17} /> : <ChevronLeft size={17} />}
          </button>
        </div>
        {!collapsed && <div className="workspace-switch"><span className="workspace-dot" /> Production workspace <ChevronLeft className="rotate-neg" size={14} /></div>}
        {!collapsed && <div className="environment-tag"><span /> DEVELOPMENT ENVIRONMENT</div>}
        <div className="nav-caption">{!collapsed && "WORKSPACE"}</div>
        <nav className="side-nav" aria-label="Main navigation">
          {navigation.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end={path === "/"}
              className={({ isActive }) => `nav-link ${isActive ? "nav-link-active" : ""}`}
              title={collapsed ? label : undefined}
              onClick={onNavigate}
            >
              <Icon size={17} strokeWidth={1.8} />
              {!collapsed && <span>{label}</span>}
              {path === "/incidents" && !collapsed && <span className="nav-count">—</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="profile-card">
            <div className="avatar">OP</div>
            {!collapsed && <div className="profile-copy"><strong>On-call operator</strong><span>Workspace member</span></div>}
            {!collapsed && <Command size={15} className="profile-shortcut" />}
          </div>
        </div>
      </aside>
    </>
  );
}
