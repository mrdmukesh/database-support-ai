import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConnectionTestResult } from "./ConnectionTestResult";

describe("ConnectionTestResult", () => {
  it("renders idle and testing states", () => {
    const { rerender } = render(<ConnectionTestResult />);
    expect(screen.getByText("Not tested")).toBeInTheDocument();
    rerender(<ConnectionTestResult isTesting />);
    expect(screen.getByText("Testing...")).toBeInTheDocument();
  });

  it("renders valid, invalid, and request-error states", () => {
    const { rerender } = render(<ConnectionTestResult result={{ connection_id: "1", is_valid: true, message: "Connection successful" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Connection successful");
    rerender(<ConnectionTestResult result={{ connection_id: "1", is_valid: false, message: "Connection error" }} />);
    expect(screen.getByRole("status")).toHaveClass("error");
    rerender(<ConnectionTestResult error="Forbidden" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Forbidden");
  });
});
