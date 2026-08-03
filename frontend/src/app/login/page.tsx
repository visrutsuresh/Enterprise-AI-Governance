"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { EyeIcon } from "@/lib/icons";
import { login } from "@/lib/useUser";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // one-time setup: shown only while the system has zero accounts
  const [needsSetup, setNeedsSetup] = useState(false);

  useEffect(() => {
    api("/auth/needs-setup")
      .then((r) => setNeedsSetup(!!r.needs_setup))
      .catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email, password);
      router.push("/tower");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function setup(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/auth/bootstrap", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await login(email, password);
      router.push("/tower");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-[100dvh] bg-[var(--parchment)] text-[var(--ink)] flex items-center justify-center px-4">
      <form onSubmit={needsSetup ? setup : submit} className="panel w-full max-w-sm px-9 py-10">
        <div className="mb-8">
          <div
            className="text-[24px] font-extrabold"
            style={{ fontFamily: "var(--font-cabinet)" }}
          >
            GOVERNANCE<span className="text-[var(--accent)]">.</span>
          </div>
          <h1 className="text-2xl font-bold mt-3">
            {needsSetup ? "First-time setup" : "Sign in"}
          </h1>
          <p className="text-sm text-[var(--ink-soft)] mt-1">
            {needsSetup
              ? "No accounts exist yet. Create the founding administrator; this screen never appears again."
              : "The AI governance control tower. No signup here: the admin creates every account."}
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
        <div className="flex items-center border-b border-[var(--line)] focus-within:border-[var(--accent)] mb-6">
          <input
            type={showPw ? "text" : "password"}
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-transparent outline-none py-2"
          />
          <button
            type="button"
            aria-label={showPw ? "Hide password" : "Show password"}
            onClick={() => setShowPw(!showPw)}
            className="text-[var(--ink-soft)] hover:text-[var(--ink)] px-1"
          >
            <EyeIcon off={showPw} />
          </button>
        </div>

        {error && <p className="text-sm text-[var(--rust)] mb-4">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="bg-[var(--accent)] hover:bg-[var(--accent-deep)] text-[#1c2126] font-semibold text-sm px-6 py-2.5 rounded-[7px] active:scale-[0.98] transition disabled:opacity-50"
        >
          {busy ? "One moment" : needsSetup ? "Create administrator" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
