import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceForm } from "./WorkspaceForm";

describe("WorkspaceForm", () => {
  it("normalizes the existing create fields", async () => {
    const onSubmit = vi.fn();
    render(<WorkspaceForm isSubmitting={false} onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Workspace name"), { target: { value: "Finance Operations" } });
    fireEvent.click(screen.getByRole("button", { name: "Create workspace" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ name: "Finance Operations", slug: "finance-operations" }));
  });
});
