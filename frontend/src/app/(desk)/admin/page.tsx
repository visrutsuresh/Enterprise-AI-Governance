"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useUser } from "@/lib/useUser";

type Person = { id: string; email: string; role: string; is_active: boolean };

export default function People() {
  const { user, loading } = useUser();
  const [people, setPeople] = useState<Person[] | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api("/users")
      .then(setPeople)
      .catch((e) => setNote(String(e)));
  }, []);

  useEffect(() => {
    if (user?.role === "admin") load();
  }, [user, load]);

  async function createReviewer(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setNote("");
    try {
      await api("/users", {
        method: "POST",
        body: JSON.stringify({ email, password, role: "reviewer" }),
      });
      setNote(`Account created for ${email}.`);
      setEmail("");
      setPassword("");
      load();
    } catch (err) {
      setNote(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function setActive(p: Person, active: boolean) {
    setBusy(true);
    setNote("");
    try {
      await api(`/users/${p.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: active }),
      });
      load();
    } catch (err) {
      setNote(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword(p: Person) {
    const pw = window.prompt(
      `New password for ${p.email} (at least 8 characters):`,
    );
    if (pw === null) return;
    if (pw.length < 8) {
      setNote("Password needs at least 8 characters.");
      return;
    }
    setBusy(true);
    setNote("");
    try {
      await api(`/users/${p.id}`, {
        method: "PATCH",
        body: JSON.stringify({ password: pw }),
      });
      setNote(`Password updated for ${p.email}.`);
    } catch (err) {
      setNote(String(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="py-9" />;
  if (!user || user.role !== "admin") {
    return (
      <main className="py-9 text-[var(--ink-soft)]">
        Only the admin can manage people.
      </main>
    );
  }
  return (
    <main className="py-9 pb-16 max-w-[760px]">
      <h1
        className="text-[28px] font-bold rise"
        style={{ "--i": 0 } as React.CSSProperties}
      >
        People
      </h1>
      <p className="text-[var(--ink-soft)] mt-1.5 mb-7">
        Reviewer accounts for this desk. There is no open signup: you create every
        account here.
      </p>

      <form
        onSubmit={createReviewer}
        className="panel flex items-end gap-3 p-5 mb-7"
      >
        <div className="flex-1">
          <label className="label block mb-1">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--accent)] outline-none py-1.5"
          />
        </div>
        <div className="flex-1">
          <label className="label block mb-1">Password</label>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-transparent border-b border-[var(--line)] focus:border-[var(--accent)] outline-none py-1.5"
          />
        </div>
        <button type="submit" disabled={busy} className="act act-acc">
          Create reviewer
        </button>
      </form>

      {note && (
        <p className="text-[13px] text-[var(--accent-deep)] mb-4">{note}</p>
      )}

      {!people ? (
        <p className="text-[var(--ink-soft)]">Loading…</p>
      ) : (
        <div className="border-t border-[var(--line)]">
          {people.map((p) => (
            <div
              key={p.id}
              className="grid grid-cols-[2fr_1fr_1fr_auto] gap-4 items-center py-3.5 px-1 border-b border-[var(--line)]"
            >
              <span className="font-semibold text-[14.5px]">{p.email}</span>
              <span className="font-array text-[11px] text-[var(--ink-soft)]">
                {p.role.toUpperCase()}
              </span>
              <span
                className={`font-array text-[11px] ${p.is_active ? "text-[var(--olive)]" : "text-[var(--rust)]"}`}
              >
                {p.is_active ? "ACTIVE" : "DEACTIVATED"}
              </span>
              <span className="flex gap-2 justify-end">
                <button
                  className="act"
                  disabled={busy}
                  onClick={() => resetPassword(p)}
                >
                  Reset password
                </button>
                {p.is_active ? (
                  p.id !== user.id && (
                    <button
                      className="act act-rej"
                      disabled={busy}
                      onClick={() => setActive(p, false)}
                    >
                      Deactivate
                    </button>
                  )
                ) : (
                  <button
                    className="act act-acc"
                    disabled={busy}
                    onClick={() => setActive(p, true)}
                  >
                    Reactivate
                  </button>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
