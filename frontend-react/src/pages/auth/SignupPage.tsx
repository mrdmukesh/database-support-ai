import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  createDefaultWorkspace,
  createOrganization,
  listOrganizations,
  signup,
} from "../../api/auth-api";
import { useAuth } from "../../hooks/use-auth";

const requiredConsents = [
  "terms_of_service",
  "privacy_policy",
  "document_processing",
  "ai_verification_required",
] as const;

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 90);
}

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Signup failed.";
}

export function SignupPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const organizationName = String(form.get("organizationName") ?? "").trim();
    const organizationSlug = String(form.get("organizationSlug") ?? "").trim() || slugify(organizationName);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    const consents = [...requiredConsents, "product_updates"].filter((key) => form.get(key));

    setError(null);
    setIsLoading(true);
    try {
      let organization;
      try {
        organization = await createOrganization({ name: organizationName, slug: organizationSlug });
      } catch (cause) {
        if (!messageOf(cause).toLowerCase().includes("already")) throw cause;
        organization = (await listOrganizations()).find((item) => item.slug === organizationSlug);
        if (!organization) throw cause;
      }

      try {
        await signup({
          organization_id: organization.id,
          email,
          password,
          full_name: String(form.get("fullName") ?? "").trim(),
          role: String(form.get("role") ?? "organization_admin"),
          consents,
          ip_address: "127.0.0.1",
        });
      } catch (cause) {
        if (!messageOf(cause).toLowerCase().includes("exists")) throw cause;
      }

      await login({ email, password });
      try {
        await createDefaultWorkspace(organization.id);
      } catch (cause) {
        if (!messageOf(cause).toLowerCase().includes("already")) throw cause;
      }
      navigate("/app/dashboard", { replace: true });
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card signup-card" aria-labelledby="signup-title">
        <p className="eyebrow">LegacyDB Support Copilot</p>
        <h1 id="signup-title">Create account</h1>
        <form onSubmit={handleSubmit} aria-describedby={error ? "signup-error" : undefined}>
          <label htmlFor="organization-name">Organization name</label>
          <input id="organization-name" name="organizationName" maxLength={200} required disabled={isLoading} />

          <label htmlFor="organization-slug">Organization slug</label>
          <input id="organization-slug" name="organizationSlug" maxLength={120} pattern="[a-z0-9][a-z0-9-]*" disabled={isLoading} />

          <label htmlFor="signup-full-name">Admin name</label>
          <input id="signup-full-name" name="fullName" required disabled={isLoading} />

          <label htmlFor="signup-email">Admin email</label>
          <input id="signup-email" name="email" type="email" maxLength={320} required disabled={isLoading} />

          <label htmlFor="signup-password">Password</label>
          <input id="signup-password" name="password" type="password" required disabled={isLoading} />

          <label htmlFor="signup-role">Role</label>
          <select id="signup-role" name="role" defaultValue="organization_admin" disabled={isLoading}>
            <option value="organization_admin">Organization Admin</option>
            <option value="dba">DBA</option>
            <option value="developer">Developer</option>
          </select>

          <fieldset disabled={isLoading}>
            <legend>Required consent</legend>
            <label><input type="checkbox" name="terms_of_service" defaultChecked required /> I agree to the Terms of Service</label>
            <label><input type="checkbox" name="privacy_policy" defaultChecked required /> I agree to the Privacy Policy</label>
            <label><input type="checkbox" name="document_processing" defaultChecked required /> I consent to processing uploaded documents</label>
            <label><input type="checkbox" name="ai_verification_required" defaultChecked required /> I understand AI-generated answers require verification</label>
            <label><input type="checkbox" name="product_updates" /> Product updates</label>
          </fieldset>

          {error ? <div id="signup-error" className="form-message error" role="alert">{error}</div> : null}
          <button type="submit" disabled={isLoading}>{isLoading ? "Creating account..." : "Create account"}</button>
        </form>
      </section>
    </main>
  );
}
