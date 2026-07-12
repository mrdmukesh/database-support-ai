import { expect, test } from "@playwright/test";

test("React shell loads", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Login" })).toBeVisible();
});
