"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/useUser";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      router.push("/docket");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-[100dvh] bg-[var(--parchment)] text-[var(--ink)] flex items-center justify-center px-4">
      <form onSubmit={submit} className="panel w-full max-w-sm px-9 py-10">
        <div className="mb-8">
          <div
            className="text-[24px] font-extrabold"
            style={{ fontFamily: "var(--font-cabinet)" }}
          >
            PAPYRUS<span className="text-[var(--accent)]">.</span>
          </div>
          <h1 className="text-2xl font-bold mt-3">Sign in</h1>
          <p className="text-sm text-[var(--ink-soft)] mt-1">
            The contract review desk. No signup here: the admin creates every
            account.
          </p>
        </div>

        <label className="label block mb-1">Email</label>
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--accent)] outline-none py-2 mb-5"
        />
        <label className="label block mb-1">Password</label>
        <input
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--accent)] outline-none py-2 mb-6"
        />

        {error && <p className="text-sm text-[var(--rust)] mb-4">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="bg-[var(--accent)] hover:bg-[var(--accent-deep)] text-white font-semibold text-sm px-6 py-2.5 rounded-[7px] active:scale-[0.98] transition disabled:opacity-50"
        >
          {busy ? "One moment" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
