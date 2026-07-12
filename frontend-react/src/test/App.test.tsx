import { describe, expect, it } from "vitest";
import { App } from "../App";
import { AuthProvider } from "../stores/auth-store";
import { renderApp, screen } from "./render";

describe("App", () => {
  it("renders the React application shell", () => {
    renderApp(
      <AuthProvider>
        <App />
      </AuthProvider>,
    );

    expect(
      screen.getByRole("heading", { name: "Login" }),
    ).toBeInTheDocument();
  });
});
