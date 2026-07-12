import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConnectionList } from "./ConnectionList";

const connection = { id: "CONN-1", organization_id: "ORG-1", workspace_id: "WS-1", engine: "mysql", name: "ERP", is_active: true };
afterEach(() => vi.restoreAllMocks());

describe("ConnectionList", () => {
  it("never displays secret fields and preserves edit prompts", () => {
    vi.spyOn(window, "prompt").mockReturnValueOnce("ERP 2").mockReturnValueOnce("");
    const onEdit = vi.fn();
    render(<ConnectionList connections={[connection]} testingIds={new Set()} testResults={{}} testErrors={{}} onEdit={onEdit} onDelete={vi.fn()} onTest={vi.fn()} />);
    expect(screen.queryByText(/secret_ref|connection_string|password/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEdit).toHaveBeenCalledWith(connection, "ERP 2", undefined);
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
});
