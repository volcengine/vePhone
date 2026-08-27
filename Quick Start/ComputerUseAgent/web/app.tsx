import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router";

import { AppShell } from "./components/app-shell";
import {
  BusinessProvider,
  businessPath,
  defaultBusiness,
  useBusinessContext,
} from "./business-context";
import { SetupPage } from "./pages/setup-page";
import { LoginPage } from "./pages/login-page";
import { TaskListPage } from "./pages/task-list-page";
import { CreateTaskPage } from "./pages/create-task-page";
import { TaskDetailPage } from "./pages/task-detail-page";
import { TaskOverviewPage } from "./pages/task-overview-page";
import { TaskReportPage } from "./pages/task-report-page";
import { TaskTracePage } from "./pages/task-trace-page";
import { PodPoolPage } from "./pages/pod-pool-page";
import { SettingsPage } from "./pages/settings-page";
import { CasesPage } from "./pages/cases-page";
import { CaseImportPreviewPage } from "./pages/case-import-preview-page";
import { CaseEditorPage } from "./pages/case-editor-page";
import { UsersPage } from "./pages/users-page";
import { TestPlanDetailPage } from "./pages/test-plan-detail-page";
import { TestPlanRunPage } from "./pages/test-plan-run-page";
import { TestPlanListPage } from "./pages/test-plan-list-page";
import { TestPlanEditorPage } from "./pages/test-plan-editor-page";
import { TaskReportListPage } from "./pages/task-report-list-page";
import { PlanExecutionReportPage } from "./pages/plan-execution-report-page";
import { api, subscribeUnauthorized } from "./api/client";
import type { SetupStatus, User } from "./api/types";
import { initializeThemePreference } from "./utils/theme";

initializeThemePreference();

function LegacyRedirect() {
  const location = useLocation();
  const businessContext = useBusinessContext();
  const businessId = businessContext?.selectedBusinessId ?? defaultBusiness().id;
  return (
    <Navigate
      to={`${businessPath(businessId, location.pathname)}${location.search}${location.hash}`}
      replace
    />
  );
}

function BusinessRoutes({ user }: { user: User }) {
  const businessContext = useBusinessContext();
  const rootPath = businessContext?.businessPath("/tasks") ?? "/tasks";
  return (
    <AppShell user={user}>
      <Routes>
        <Route index element={<Navigate to="tasks" replace />} />
        <Route path="tasks">
          <Route index element={<TaskListPage />} />
          <Route path="new" element={<CreateTaskPage />} />
          <Route path=":taskId" element={<TaskDetailPage />}>
            <Route index element={<TaskOverviewPage />} />
            <Route path="report" element={<TaskReportPage />} />
            <Route path="trace" element={<TaskTracePage />} />
          </Route>
        </Route>
        <Route path="cases">
          <Route index element={<CasesPage />} />
          <Route path="new" element={<CaseEditorPage />} />
          <Route path="import/preview" element={<CaseImportPreviewPage />} />
          <Route path=":caseId/edit" element={<CaseEditorPage />} />
        </Route>
        <Route path="test-plans">
          <Route index element={<TestPlanListPage />} />
          <Route path="new" element={<TestPlanEditorPage />} />
          <Route path=":planId" element={<TestPlanDetailPage />} />
          <Route path=":planId/run" element={<TestPlanRunPage />} />
          <Route path=":planId/edit" element={<TestPlanEditorPage />} />
        </Route>
        <Route path="task-reports">
          <Route index element={<TaskReportListPage />} />
          <Route path=":executionId" element={<PlanExecutionReportPage />} />
        </Route>
        <Route path="pods" element={<PodPoolPage />} />
        <Route
          path="users"
          element={user.role === "admin" ? <UsersPage /> : <Navigate to={rootPath} replace />}
        />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="tasks" replace />} />
      </Routes>
    </AppShell>
  );
}

function AuthGate() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useEffect(
    () => subscribeUnauthorized(() => {
      queryClient.setQueryData(["me"], null);
    }),
    [queryClient],
  );

  const setupStatus = useQuery({
    queryKey: ["setup-status"],
    queryFn: () => api.get<SetupStatus>("/setup/status"),
    retry: false,
  });

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<User>("/auth/me"),
    retry: false,
    enabled: setupStatus.data?.initialized === true,
  });

  if (setupStatus.isLoading) {
    return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "#64748b", fontSize: "0.875rem" }}>加载中...</div>;
  }

  if (!setupStatus.data?.initialized) {
    return (
      <SetupPage
        onAlreadyInitialized={() => {
          queryClient.setQueryData(["setup-status"], { initialized: true });
          setupStatus.refetch();
        }}
        onAuthenticated={(user) => {
          queryClient.setQueryData(["me"], user);
          queryClient.setQueryData(["setup-status"], { initialized: true });
          navigate(businessPath(defaultBusiness().id, "/tasks"), { replace: true });
        }}
      />
    );
  }

  if (me.isLoading) {
    return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: "#64748b", fontSize: "0.875rem" }}>加载中...</div>;
  }

  if (!me.data) {
    return (
      <LoginPage
        onAuthenticated={(user) => {
          queryClient.setQueryData(["me"], user);
          navigate(businessPath(defaultBusiness().id, "/tasks"), { replace: true });
        }}
      />
    );
  }

  return (
    <BusinessProvider>
      <Routes>
        <Route path="biz/:businessId/*" element={<BusinessRoutes user={me.data} />} />
        <Route path="*" element={<LegacyRedirect />} />
      </Routes>
    </BusinessProvider>
  );
}

export function App() {
  return <AuthGate />;
}
