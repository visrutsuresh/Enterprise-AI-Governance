"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { API_BASE, upload } from "@/lib/api";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { api, readable } from "@/lib/api";
import { sevClass } from "@/lib/stages";

type EvidenceFile = {
  id: number;
  filename: string;
  size: number;
  uploaded_by: string | null;
};

type Finding = {
  finding_id: string;
  asset_id: string;
  asset_name: string | null;
  risk_tier: string | null;
  inspector: string | null;
  control_id: string | null;
  severity: string | null;
  plain: string | null;
  remediation: string | null;
  status: string;
  owner: string | null;
  due_at: string | null;
  routed_to: string | null;
  evidence_files: EvidenceFile[];
  overdue: boolean;
  review: { verdict?: string } | null;
};

type Person = { email: string; role: string };

type Board = {
  findings: Finding[];
  counts: Record<string, number>;
  overdue: number;
  unassigned: number;
};

// dismissed is deliberately absent: dismissing needs a written reason, so it stays
// on the override path. There is no column to drag a finding into.
const COLUMNS = [
  { key: "open", label: "OPEN" },
  { key: "in_progress", label: "IN PROGRESS" },
  { key: "awaiting_evidence", label: "AWAITING EVIDENCE" },
  { key: "closed", label: "CLOSED" },
] as const;

const SCOPES = [
  { key: "mine", label: "MINE" },
  { key: "unassigned", label: "UNASSIGNED" },
  { key: "overdue", label: "OVERDUE" },
  { key: "all", label: "ALL" },
] as const;

// severity is shared with the rest of the app: solid / outlined / bare, no hue

function dueLabel(f: Finding) {
  if (!f.due_at) return "no date";
  const d = new Date(f.due_at);
  if (Number.isNaN(d.getTime())) return "bad date";
  // the year used to be omitted, so a deadline next month and one a year out
  // both read "03 SEP" on a board whose whole point is deadlines
  const sameYear = d.getFullYear() === new Date().getFullYear();
  const txt = d
    .toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      ...(sameYear ? {} : { year: "numeric" }),
    })
    .toUpperCase();
  return f.overdue ? `LATE ${txt}` : txt;
}

const kb = (n: number) =>
  n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${Math.round(n / 1024)} KB` : `${(n / 1048576).toFixed(1)} MB`;

/* ------------------------------------------------------- evidence on a card */

function Evidence({ f, onUploaded }: { f: Finding; onUploaded: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const picker = useRef<HTMLInputElement>(null);
  const files = f.evidence_files ?? [];

  async function send(file: File) {
    setErr("");
    setBusy(true);
    try {
      await upload(`/flags/${f.finding_id}/evidence`, file);
      onUploaded();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      if (picker.current) picker.current.value = ""; // let the same file be re-picked after a failure
    }
  }

  return (
    <div className="mt-2 pt-2 border-t border-[var(--line)]">
      <button
        onClick={() => setOpen(!open)}
        className={`font-array text-[13px] tracking-wider hover:underline ${
          files.length ? "text-[var(--olive)]" : "text-[var(--ink-soft)]"
        }`}
      >
        {files.length ? `EVIDENCE ${files.length}` : "NO EVIDENCE"}
      </button>

      {open && (
        <div className="mt-2">
          {files.map((e) => (
            <a
              key={e.id}
              href={`${API_BASE}/evidence/${e.id}`}
              className="block font-array text-[13px] text-[var(--accent)] hover:underline truncate"
              title={`${e.filename} · ${kb(e.size)} · ${e.uploaded_by ?? "unknown"}`}
            >
              {e.filename} · {kb(e.size)}
            </a>
          ))}
          <input
            ref={picker}
            type="file"
            className="hidden"
            onChange={(ev) => ev.target.files?.[0] && send(ev.target.files[0])}
          />
          <button
            onClick={() => picker.current?.click()}
            disabled={busy}
            className="font-array text-[13px] tracking-wider text-[var(--accent)] hover:underline mt-1 disabled:opacity-50"
          >
            {busy ? "UPLOADING…" : "+ ATTACH PROOF"}
          </button>
          {err && <p className="font-array text-[13px] text-[var(--rust)] mt-1 leading-snug">{err}</p>}
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- one card */

function Card({
  f,
  onOwner,
  people,
  onDue,
  onUploaded,
  dragging,
}: {
  f: Finding;
  onOwner: (f: Finding, owner: string | null) => void;
  people: Person[];
  onDue: (f: Finding, due: string) => void;
  onUploaded: () => void;
  dragging?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: f.finding_id });
  const router = useRouter();

  return (
    <div
      ref={setNodeRef}
      style={transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` } : undefined}
      className={`panel p-3 mb-2 ${isDragging || dragging ? "opacity-40" : ""}`}
    >
      {/* the grip is the drag handle. The footer controls are NOT, or every
          click on the date picker would start a drag instead.
          It is ALSO the way into the asset: the card used to look clickable all
          over while only the 9.5px asset name navigated. The 5px drag threshold
          below means a click stays a click. */}
      <div
        {...attributes}
        {...listeners}
        role="link"
        tabIndex={0}
        title={`Open ${f.asset_name ?? f.asset_id}`}
        onClick={() => !isDragging && router.push(`/assets/${f.asset_id}`)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            router.push(`/assets/${f.asset_id}`);
          }
        }}
        className="cursor-pointer active:cursor-grabbing rounded -mx-1 px-1 hover:bg-[var(--wash)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
      >
        <span
          className={sevClass(f.severity)}
        >
          {(f.severity ?? "—").toUpperCase()}
        </span>
        <p className="text-[13px] font-semibold mt-2 leading-snug">{f.plain}</p>
        <p className="font-array text-[13px] text-[var(--ink-soft)] mt-1">
          {f.control_id} · {f.inspector}
        </p>
      </div>

      <Link
        href={`/assets/${f.asset_id}`}
        className="font-array text-[13px] text-[var(--accent)] hover:underline mt-1 inline-block"
      >
        {f.asset_name ?? f.asset_id}
      </Link>

      <div className="flex items-center gap-2 mt-3 pt-2 border-t border-[var(--line)]">
        {/* was a single ASSIGN TO ME button, so a board with three reviewers on it
            could only ever assign work to whoever was looking at the screen */}
        <label className="sr-only" htmlFor={`owner-${f.finding_id}`}>Owner</label>
        <select
          id={`owner-${f.finding_id}`}
          value={f.owner ?? ""}
          onChange={(e) => onOwner(f, e.target.value || null)}
          title={f.owner ? `Assigned to ${f.owner}` : "Unassigned"}
          className="bg-transparent font-array text-[13px] text-[var(--accent)] outline-none max-w-[180px] truncate"
        >
          <option value="">unassigned</option>
          {people.map((p) => (
            <option key={p.email} value={p.email}>
              {p.email}
            </option>
          ))}
          {/* an owner the agent wrote as a display name is not in the account
              list; keep it visible rather than silently showing "unassigned" */}
          {f.owner && !people.some((p) => p.email === f.owner) && (
            <option value={f.owner}>{f.owner}</option>
          )}
        </select>
        <input
          type="date"
          value={f.due_at ? String(f.due_at).slice(0, 10) : ""}
          onChange={(e) => onDue(f, e.target.value)}
          className={`ml-auto bg-transparent font-array text-[13px] outline-none ${
            f.overdue ? "text-[var(--rust)] font-bold" : "text-[var(--ink-soft)]"
          }`}
          title={dueLabel(f)}
        />
      </div>

      <Evidence f={f} onUploaded={onUploaded} />
    </div>
  );
}

/* -------------------------------------------------------------- one column */

function Column({
  col,
  findings,
  ...rest
}: {
  col: (typeof COLUMNS)[number];
  findings: Finding[];
  onOwner: (f: Finding, owner: string | null) => void;
  people: Person[];
  onDue: (f: Finding, due: string) => void;
  onUploaded: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key });
  return (
    <div
      ref={setNodeRef}
      className={`rounded-[var(--radius)] p-3 transition-colors ${
        isOver ? "bg-[var(--accent-wash)]" : "bg-[var(--wash)]"
      }`}
    >
      <div className="flex justify-between font-array text-[13px] tracking-[0.09em] text-[var(--ink-soft)] mb-3">
        <span>{col.label}</span>
        <span>{findings.length}</span>
      </div>
      {findings.map((f) => (
        <Card key={f.finding_id} f={f} {...rest} />
      ))}
      {findings.length === 0 && (
        <p className="font-array text-[13px] text-[var(--ink-soft)] opacity-50 py-4 text-center">
          nothing here
        </p>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- the page */

export default function Remediation() {
  const [board, setBoard] = useState<Board | null>(null);
  const [people, setPeople] = useState<Person[]>([]);
  const [scope, setScope] = useState<string>("mine");
  const [team, setTeam] = useState("");
  const [error, setError] = useState("");
  const [dragId, setDragId] = useState<string | null>(null);
  const sensors = useSensors(
    // a small threshold so a click on a card is a click, not a one-pixel drag
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );
  const scopeRef = useRef(scope);
  scopeRef.current = scope;

  const load = useCallback(async () => {
    const p = new URLSearchParams();
    if (scope === "mine") p.set("mine", "true");
    if (scope === "unassigned") p.set("unassigned", "true");
    if (scope === "overdue") p.set("overdue", "true");
    if (team) p.set("team", team);
    try {
      setBoard(await api(`/remediation?${p}`));
      setError(""); // one failed poll used to leave the banner up for the session
    } catch (e) {
      setError(readable(e));
    }
  }, [scope, team]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    // who work can be handed to. Fetched once: the roster does not change while
    // someone triages a board.
    api("/users/assignable").then(setPeople).catch(() => setPeople([]));
  }, []);

  const teams = useMemo(() => {
    const s = new Set<string>();
    board?.findings.forEach((f) => f.routed_to && s.add(f.routed_to));
    return [...s].sort();
  }, [board]);

  // one place that writes a change and repairs the screen if the server says no
  async function patch(f: Finding, body: Record<string, unknown>, optimistic: Partial<Finding>) {
    const before = board;
    setError("");
    setBoard((b) =>
      b
        ? {
            ...b,
            findings: b.findings.map((x) =>
              x.finding_id === f.finding_id ? { ...x, ...optimistic } : x,
            ),
          }
        : b,
    );
    try {
      await api(`/flags/${f.finding_id}`, { method: "PATCH", body: JSON.stringify(body) });
      load(); // re-read so counts, overdue flags and filters are the server's truth
    } catch (e) {
      setBoard(before); // put the card back where it was
      const msg = String(e);
      setError(
        msg.includes("409")
          ? "That finding was dismissed by an override, so it cannot be moved. Reopen it through the asset instead."
          : `That change did not save: ${msg}`,
      );
    }
  }

  function onDragEnd(ev: DragEndEvent) {
    setDragId(null);
    const to = String(ev.over?.id ?? "");
    const f = board?.findings.find((x) => x.finding_id === ev.active.id);
    if (!f || !to || to === f.status) return;
    patch(f, { status: to }, { status: to });
  }

  const rowsView = scope === "all";

  if (error && !board)
    return <main className="py-9 text-[var(--rust)]">{error}</main>;

  return (
    <main className="py-9">
      <div className="flex items-baseline gap-4">
        <h1 className="text-[30px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
          Remediation
        </h1>
        {board && (
          <span className="font-array text-[13px] text-[var(--ink-soft)]">
            {board.findings.length} FINDINGS · {board.overdue} OVERDUE ·{" "}
            {board.unassigned} UNASSIGNED
          </span>
        )}
      </div>
      <p className="text-[13px] text-[var(--ink-soft)] mt-2 max-w-[70ch]">
        A confirmed finding is not a fixed one. This is where an accepted flag gets an
        owner, a deadline and a state that moves, and every one of those changes joins
        the asset&apos;s audit chain.
      </p>

      <div className="flex items-center gap-2 mt-5 flex-wrap">
        {SCOPES.map((s) => (
          <button
            key={s.key}
            onClick={() => setScope(s.key)}
            className={`font-array text-[13px] tracking-wider px-3 py-[6px] rounded-[3px] border transition-colors ${
              scope === s.key
                ? "bg-[var(--accent-wash)] text-[var(--accent)] border-[var(--accent)]"
                : "text-[var(--ink-soft)] border-[var(--line)] hover:text-[var(--ink)]"
            }`}
          >
            {s.label}
          </button>
        ))}
        {teams.length > 0 && (
          <select
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            className="font-array text-[13px] tracking-wider bg-transparent border border-[var(--line)] rounded-[3px] px-3 py-[6px] outline-none text-[var(--ink-soft)]"
          >
            <option value="">ANY TEAM</option>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t.toUpperCase()}
              </option>
            ))}
          </select>
        )}
      </div>

      {error && (
        <p className="attn-note mt-4 text-[13px]" role="alert">
          {error}
        </p>
      )}

      {!board ? (
        <p className="text-[var(--ink-soft)] mt-6">Loading the work…</p>
      ) : rowsView ? (
        /* the whole estate is ~200 findings: four columns of that is unusable,
           so the ALL view is a list. Same data, same endpoint. */
        <div className="panel mt-5 overflow-hidden">
          <div className="grid grid-cols-[110px_minmax(0,1fr)_180px_150px_110px_100px] gap-4 px-4 py-3 font-array text-[13px] tracking-[0.09em] text-[var(--ink-soft)] border-b border-[var(--line)]">
            <span>SEVERITY</span>
            <span>FINDING</span>
            <span>ASSET</span>
            <span>OWNER</span>
            <span>DUE</span>
            <span>STATUS</span>
          </div>
          {board.findings.map((f) => (
            <div
              key={f.finding_id}
              className="grid grid-cols-[110px_minmax(0,1fr)_180px_150px_110px_100px] gap-4 px-4 py-3 items-center border-b border-[var(--line)] last:border-0"
            >
              <span
                className={`${sevClass(f.severity)} justify-self-start`}
              >
                {(f.severity ?? "—").toUpperCase()}
              </span>
              <span>
                <span className="block text-[13px] font-semibold">{f.plain}</span>
                <span className="block font-array text-[13px] text-[var(--ink-soft)] mt-[2px]">
                  {f.control_id} · {f.inspector}
                  {f.evidence_files?.length ? (
                    <span className="text-[var(--olive)]"> · {f.evidence_files.length} EVIDENCE</span>
                  ) : null}
                </span>
              </span>
              <Link
                href={`/assets/${f.asset_id}`}
                className="font-array text-[13px] text-[var(--accent)] hover:underline truncate"
              >
                {f.asset_name ?? f.asset_id}
              </Link>
              <span className="font-array text-[13px] text-[var(--ink-soft)] truncate">
                {f.owner ?? "unassigned"}
              </span>
              <span
                className={`font-array text-[13px] ${f.overdue ? "text-[var(--rust)] font-bold" : "text-[var(--ink-soft)]"}`}
              >
                {dueLabel(f)}
              </span>
              <span className="font-array text-[13px] tracking-wider text-[var(--ink-soft)]">
                {f.status.replace("_", " ").toUpperCase()}
              </span>
            </div>
          ))}
          {board.findings.length === 0 && (
            <p className="text-[var(--ink-soft)] p-6 text-[13px]">
              {/* this is the ALL view, so the only thing that can be hiding rows
                  is the team selector. With no team chosen the board is genuinely
                  empty, and blaming a filter nobody set would send them hunting */}
              {team
                ? "No findings for that team. Clear the team filter to see the whole board."
                : "No findings yet. They appear here once an assessment flags something."}
            </p>
          )}
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          onDragStart={(e: DragStartEvent) => setDragId(String(e.active.id))}
          onDragEnd={onDragEnd}
          onDragCancel={() => setDragId(null)}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-5 items-start">
            {COLUMNS.map((col) => (
              <Column
                key={col.key}
                col={col}
                findings={board.findings.filter((f) => f.status === col.key)}
                onOwner={(f, owner) => patch(f, { owner }, { owner })}
                people={people}
                onDue={(f, due) => patch(f, { due_at: due || null }, { due_at: due || null })}
                onUploaded={load}
              />
            ))}
          </div>
          <DragOverlay>
            {dragId ? (
              <div className="panel p-3 rotate-[1.5deg] border-2 border-[var(--ink)]">
                <p className="text-[13px] font-semibold">
                  {board.findings.find((f) => f.finding_id === dragId)?.plain}
                </p>
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}
    </main>
  );
}
