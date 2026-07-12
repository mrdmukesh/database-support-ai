import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DocumentList } from "./DocumentList";

describe("DocumentList", () => {
  it("renders title, version, and associated workspace", () => {
    render(<DocumentList
      documents={[{ id: "D1", organization_id: "O1", workspace_id: "W1", title: "Runbook", current_version: 2 }]}
      workspaces={[{ id: "W1", organization_id: "O1", name: "Finance", slug: "finance", is_active: true }]}
    />);
    expect(screen.getByText("Runbook")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
  });
});
