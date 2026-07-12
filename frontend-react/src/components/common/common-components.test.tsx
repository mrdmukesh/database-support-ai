import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmationDialog } from "./ConfirmationDialog";
import { EmptyState } from "./EmptyState";
import { ErrorMessage } from "./ErrorMessage";
import { LoadingState } from "./LoadingState";
import { StatusBadge } from "./StatusBadge";

describe("shared status components", () => {
  it("preserves loading, error, and empty meanings", () => {
    render(<><LoadingState message="Loading records..." /><ErrorMessage message="Request failed" /><EmptyState message="No records." /></>);
    expect(screen.getByRole("status")).toHaveTextContent("Loading records...");
    expect(screen.getByRole("alert")).toHaveTextContent("Request failed");
    expect(screen.getByText("No records.")).toHaveClass("empty-state");
  });
  it("renders only an explicit status without deriving AI meaning", () => {
    render(<StatusBadge status="DEVELOPER_REVIEW" />);
    expect(screen.getByText("DEVELOPER_REVIEW")).toHaveAttribute("data-status", "DEVELOPER_REVIEW");
  });
  it("keeps a closed confirmation absent and supports explicit cancel or confirm", () => {
    const confirm=vi.fn(), cancel=vi.fn(); const view=render(<ConfirmationDialog open={false} title="Delete" message="Keep history?" onConfirm={confirm} onCancel={cancel} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    view.rerender(<ConfirmationDialog open title="Delete" message="Keep history?" onConfirm={confirm} onCancel={cancel} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" })); fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(cancel).toHaveBeenCalledOnce(); expect(confirm).toHaveBeenCalledOnce();
  });
  it("moves focus into dialogs, exposes its description, closes on Escape, and restores focus", () => {
    const cancel=vi.fn(); const trigger=document.createElement("button"); document.body.appendChild(trigger); trigger.focus();
    const view=render(<ConfirmationDialog open title="Deactivate" message="Existing history is kept." onConfirm={vi.fn()} onCancel={cancel} />);
    const dialog=screen.getByRole("dialog", { name: "Deactivate", description: "Existing history is kept." });
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" }); expect(cancel).toHaveBeenCalledOnce();
    view.unmount(); expect(trigger).toHaveFocus(); trigger.remove(); expect(dialog).not.toBeInTheDocument();
  });
});
