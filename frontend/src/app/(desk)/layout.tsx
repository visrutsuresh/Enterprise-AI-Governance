"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { logout, useUser } from "@/lib/useUser";

export default function DeskLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useUser();
  const router = useRouter();
  const pathname = usePathname();
  const [brand, setBrand] = useState("Governance");

  useEffect(() => {
    if (loading) return;
    if (!user) router.replace("/login");
  }, [user, loading, router]);

  useEffect(() => {
    api("/config")
      .then((c) => c.brand_name && setBrand(c.brand_name))
      .catch(() => {});
  }, []);

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  if (loading || !user)
    return <main className="min-h-[100dvh] bg-[var(--parchment)]" />;
  const onTower = pathname === "/tower" || pathname.startsWith("/assets");
  const onPeople = pathname === "/admin";
  const linkCls = (on: boolean) =>
    `text-[13.5px] font-medium pb-1 border-b-2 transition-colors ${
      on
        ? "text-[var(--ink)] border-[var(--accent)]"
        : "text-[var(--ink-soft)] border-transparent hover:text-[var(--ink)]"
    }`;

  return (
    <div className="min-h-[100dvh] bg-[var(--parchment)]">
      <div className="max-w-[1400px] mx-auto px-10">
        <header className="flex items-center gap-7 py-5 border-b border-[var(--line)]">
          <div
            className="text-[21px] font-extrabold tracking-[0.02em]"
            style={{ fontFamily: "var(--font-cabinet)" }}
          >
            {brand.toUpperCase()}
            <span className="text-[var(--accent)]">.</span>
          </div>
          <nav className="flex gap-6 ml-6">
            <Link href="/tower" className={linkCls(onTower)}>
              Control tower
            </Link>
            {user.role === "admin" && (
              <Link href="/admin" className={linkCls(onPeople)}>
                People
              </Link>
            )}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-[13px] text-[var(--ink-soft)]">
            <span>{user.email}</span>
            <span
              className="w-7 h-7 rounded-full bg-[var(--accent)] text-white grid place-items-center text-[12px] font-bold"
              style={{ fontFamily: "var(--font-cabinet)" }}
            >
              {user.email.slice(0, 2).toUpperCase()}
            </span>
            <button
              onClick={signOut}
              className="text-[13px] underline underline-offset-4 hover:text-[var(--accent)]"
            >
              Sign out
            </button>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
