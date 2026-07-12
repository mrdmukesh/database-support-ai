import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "../layouts/AppLayout";
import { LoginPage } from "../pages/auth/LoginPage";
import { SignupPage } from "../pages/auth/SignupPage";
import { WorkspacesPage } from "../pages/workspaces/WorkspacesPage";
import { ConnectionsPage } from "../pages/connections/ConnectionsPage";
import { DocumentsPage } from "../pages/documents/DocumentsPage";
import { DashboardPage } from "../pages/dashboard/DashboardPage";
import { InvestigationPage } from "../pages/investigations/InvestigationPage";
import { InvestigationResultPage } from "../pages/investigations/InvestigationResultPage";
import { ReportViewerPage } from "../pages/reports/ReportViewerPage";
import { InvestigationHistoryPage } from "../pages/investigations/InvestigationHistoryPage";
import { LearningPage } from "../pages/learning/LearningPage";
import {
  NotFoundPage,
} from "../pages/migration-placeholders";
import { ProtectedRoute } from "./protected-route";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="workspaces" element={<WorkspacesPage />} />
          <Route path="connections" element={<ConnectionsPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="investigations" element={<InvestigationPage />} />
          <Route path="investigations/:investigationId" element={<InvestigationResultPage />} />
          <Route path="investigations/history" element={<InvestigationHistoryPage />} />
          <Route path="reports/view" element={<ReportViewerPage />} />
          <Route path="learning" element={<LearningPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
