import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConnectionForm } from "./ConnectionForm";

const workspace = { id: "WS-1", organization_id: "ORG-1", name: "Finance", slug: "finance", is_active: true };

describe("ConnectionForm", () => {
  it("preserves database fields and keeps connection strings masked and transient", async () => {
    const onSubmit = vi.fn();
    render(<ConnectionForm organizationId="ORG-1" workspaces={[workspace]} isSubmitting={false} onSubmit={onSubmit} />);
    expect(screen.getByLabelText("Connection string")).toHaveAttribute("type", "password");
    fireEvent.change(screen.getByLabelText("Engine"), { target: { value: "mysql" } });
    fireEvent.change(screen.getByLabelText("Connection name"), { target: { value: "ERP" } });
    fireEvent.change(screen.getByLabelText("Connection string"), { target: { value: "mysql://user:password@db/erp" } });
    fireEvent.click(screen.getByRole("button", { name: "Add connection" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
      organization_id: "ORG-1",
      workspace_id: "WS-1",
      engine: "mysql",
      name: "ERP",
      connection_string: "mysql://user:password@db/erp",
    })));
    expect(screen.getByLabelText("Connection string")).toHaveValue("");
  });

  it("preserves all currently supported database types", () => {
    render(<ConnectionForm organizationId="ORG-1" workspaces={[workspace]} isSubmitting={false} onSubmit={vi.fn()} />);
    expect(screen.getAllByRole("option").map((option) => option.getAttribute("value"))).toEqual([
      "WS-1", "sql_server", "postgresql", "mysql", "sqlite", "oracle",
    ]);
  });
});
