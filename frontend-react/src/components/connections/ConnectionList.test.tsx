import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConnectionList } from "./ConnectionList";

const connection = {
  id: "CONN-1", organization_id: "ORG-1", workspace_id: "WS-1", engine: "mysql",
  name: "ERP", environment_type: "production" as const, max_scan_rows: 500, is_active: true,
};
const sqlConnection = { ...connection, id: "SQL-CONN-1", engine: "sql_server", name: "SQL App" };
afterEach(() => vi.restoreAllMocks());

describe("ConnectionList", () => {
  it("never displays secret fields and preserves edit prompts", () => {
    vi.spyOn(window, "prompt").mockReturnValueOnce("ERP 2").mockReturnValueOnce("");
    const onEdit = vi.fn();
    render(<ConnectionList connections={[connection]} testingIds={new Set()} testResults={{}} testErrors={{}} onEdit={onEdit} onDelete={vi.fn()} onTest={vi.fn()} />);
    expect(screen.queryByText(/secret_ref|connection_string|password/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEdit).toHaveBeenCalledWith(connection, "ERP 2", "production", undefined);
  });

  it("preserves delete confirmation and exposes connection testing", () => {
    const onDelete = vi.fn();
    const onTest = vi.fn();
    render(<ConnectionList connections={[connection]} testingIds={new Set()} testResults={{}} testErrors={{}} onEdit={vi.fn()} onDelete={onDelete} onTest={onTest} />);
    fireEvent.click(screen.getByRole("button", { name: "Test" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onTest).toHaveBeenCalledWith(connection);
    expect(screen.getByRole("dialog")).toHaveTextContent("Deactivate this database connection? Existing history is kept.");
    fireEvent.click(screen.getByRole("dialog").querySelector("button:last-child")!);
    expect(onDelete).toHaveBeenCalledWith(connection);
  });

  it("shows discovery for SQL Server and sends the exact selected connection", () => {
    const onRefreshMetadata = vi.fn();
    render(<ConnectionList connections={[sqlConnection]} testingIds={new Set()} testResults={{}} testErrors={{}} onEdit={vi.fn()} onDelete={vi.fn()} onTest={vi.fn()} metadata={{ [sqlConnection.id]: { status: "NOT_DISCOVERED", version: null, last_refresh: null, counts: {}, completeness: {} } }} onRefreshMetadata={onRefreshMetadata} />);
    fireEvent.click(screen.getByRole("button", { name: "Discover Metadata" }));
    expect(onRefreshMetadata).toHaveBeenCalledTimes(1);
    expect(onRefreshMetadata).toHaveBeenCalledWith(sqlConnection);
    expect(screen.getByText("Metadata Status:").parentElement).toHaveTextContent("NOT_DISCOVERED");
  });

  it("shows counts and disables repeated refresh clicks while refreshing", () => {
    const onRefreshMetadata = vi.fn();
    render(<ConnectionList connections={[sqlConnection]} testingIds={new Set()} testResults={{}} testErrors={{}} onEdit={vi.fn()} onDelete={vi.fn()} onTest={vi.fn()} metadata={{ [sqlConnection.id]: { status: "READY", version: 3, last_refresh: "2026-08-09T19:30:00Z", counts: { tables: 6, columns: 42, procedures: 8, views: 1, functions: 2, triggers: 1, relationships: 14 }, completeness: {} } }} refreshingIds={new Set([sqlConnection.id])} onRefreshMetadata={onRefreshMetadata} />);
    const button = screen.getByRole("button", { name: "Refreshing..." });
    expect(button).toBeDisabled();
    expect(screen.getByText(/Tables: 6; Columns: 42/)).toBeInTheDocument();
    expect(screen.getByText("Metadata Status:").parentElement).toHaveTextContent("Refreshing");
    fireEvent.click(button);
    expect(onRefreshMetadata).not.toHaveBeenCalled();
  });
});
