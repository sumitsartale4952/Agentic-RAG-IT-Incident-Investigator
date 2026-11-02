import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar.jsx";
import Topbar from "./Topbar.jsx";

export default function AppLayout({ health, onRefreshHealth, notify }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <div className="app-shell min-h-screen">
      <Sidebar
        collapsed={collapsed}
        onToggle={() => setCollapsed((value) => !value)}
        mobileOpen={mobileOpen}
        onNavigate={() => setMobileOpen(false)}
      />
      <div className={`app-main ${collapsed ? "app-main-wide" : ""}`}>
        <Topbar
          health={health}
          onRefreshHealth={onRefreshHealth}
          onOpenMobileNav={() => setMobileOpen(true)}
        />
        <div className="page-scroll"><Outlet context={{ notify, health }} /></div>
      </div>
    </div>
  );
}
