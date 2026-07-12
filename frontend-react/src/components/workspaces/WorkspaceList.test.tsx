import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WorkspaceList } from "./WorkspaceList";

const workspace = { id: "WS-1", organization_id: "ORG-1", name: "Finance", slug: "finance", is_active: true };

afterEach(() => vi.restoreAllMocks());

describe("WorkspaceList", () => {
  it("renders and selects a workspace when selection is supported", () => {
    const onSelect = vi.fn();
    render(<WorkspaceList workspaces={[workspace]} onSelect={onSelect} onEdit={vi.fn()} onDelete={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Select" }));

    expect(onSelect).toHaveBeenCalledWith(workspace);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("preserves prompt-based edit behavior", () => {
    vi.spyOn(window, "prompt").mockReturnValueOnce("Finance Ops").mockReturnValueOnce("finance-ops");
    const onEdit = vi.fn();
    render(<WorkspaceList workspaces={[workspace]} onEdit={onEdit} onDelete={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(window.prompt).toHaveBeenNthCalledWith(1, "Workspace name", "Finance");
    expect(window.prompt).toHaveBeenNthCalledWith(2, "Workspace slug", "finance");
    expect(onEdit).toHaveBeenCalledWith(workspace, "Finance Ops", "finance-ops");
  });

  it("preserves delete confirmation and cancellation", () => {
    const onDelete = vi.fn();
    render(<WorkspaceList workspaces={[workspace]} onEdit={vi.fn()} onDelete={onDelete} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("Deactivate this workspace? Existing history is kept.");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onDelete).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("dialog").querySelector("button:last-child")!);
    expect(onDelete).toHaveBeenCalledWith(workspace);
  });
});
