import { Outlet } from "react-router-dom";
import { Header } from "../components/navigation/Header";
import { Sidebar } from "../components/navigation/Sidebar";

export function AppLayout() {
  return (
    <div className="application-layout">
      <Sidebar />
      <div className="application-content">
        <Header />
        <main className="application-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
