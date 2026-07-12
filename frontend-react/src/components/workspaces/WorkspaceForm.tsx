import { useState, type FormEvent } from "react";

export interface WorkspaceFormValue {
  name: string;
  slug: string;
}

interface WorkspaceFormProps {
  isSubmitting: boolean;
  onSubmit: (value: WorkspaceFormValue) => Promise<void> | void;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 90);
}

export function WorkspaceForm({ isSubmitting, onSubmit }: WorkspaceFormProps) {
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({ name: name.trim(), slug: slugify(slug.trim() || name) });
    setName("");
    setSlug("");
  }

  return (
    <form className="workspace-form" onSubmit={handleSubmit}>
      <h2>Create workspace</h2>
      <label htmlFor="workspace-name">Workspace name</label>
      <input
        id="workspace-name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        maxLength={200}
        disabled={isSubmitting}
        required
      />
      <label htmlFor="workspace-slug">Workspace slug</label>
      <input
        id="workspace-slug"
        value={slug}
        onChange={(event) => setSlug(event.target.value)}
        maxLength={120}
        pattern="[a-z0-9][a-z0-9-]*"
        disabled={isSubmitting}
      />
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating..." : "Create workspace"}
      </button>
    </form>
  );
}
