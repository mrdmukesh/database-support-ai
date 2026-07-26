import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExecutiveSummarySection } from "./ExecutiveSummarySection";

describe("ExecutiveSummarySection", () => {
  it("shows a short summary fully without progressive disclosure", () => {
    render(<ExecutiveSummarySection summary="Verified evidence was collected. Root cause was not established." />);
    expect(screen.getByText("Verified evidence was collected.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Read more" })).not.toBeInTheDocument();
  });

  it("collapses a long summary, expands it, and collapses it again", () => {
    const full = Array.from({ length: 9 }, (_, index) => `Evidence statement ${index + 1} confirms SQL-${index + 1}.`).join(" ");
    render(<ExecutiveSummarySection summary={full} />);
    const toggle = screen.getByRole("button", { name: "Read more" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.querySelector(".executive-summary-collapsed")).not.toHaveTextContent("Evidence statement 9");
    fireEvent.click(toggle);
    expect(document.querySelector(".executive-summary-card > .executive-summary-full")).toHaveTextContent("Evidence statement 9 confirms SQL-9.");
    fireEvent.click(screen.getByRole("button", { name: "Show less" }));
    expect(screen.getByRole("button", { name: "Read more" })).toHaveAttribute("aria-expanded", "false");
  });

  it("formats known labels as safe structured headings and preserves evidence references", () => {
    render(<ExecutiveSummarySection summary={"Verified findings: SQL-1 returned 100 rows. Confidence note: Medium confidence. Recommended next questions: Review SQL-2?"} />);
    expect(screen.getByRole("heading", { name: "Verified findings" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Confidence" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recommended next questions" })).toBeInTheDocument();
    expect(screen.getByText(/SQL-1 returned 100 rows/)).toBeInTheDocument();
  });

  it("renders untrusted HTML only as text", () => {
    render(<ExecutiveSummarySection summary={'<img src=x onerror="alert(1)"> verified.'} />);
    expect(document.querySelector("img")).toBeNull();
    expect(screen.getByText(/<img src=x onerror/)).toBeInTheDocument();
  });
});
