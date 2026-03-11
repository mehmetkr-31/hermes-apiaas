/// <reference lib="dom" />
import { createCliRenderer, TextAttributes } from "@opentui/core";
import { createRoot, useKeyboard } from "@opentui/react";
import { useState, useEffect, useRef } from "react";
import path from "path";

const ROOT_DIR = path.resolve(import.meta.dir, "../../../");

const MANAGER_URL = "http://127.0.0.1:9000";

// Auto-start the Manager if not running
function ensureManagerRunning() {
  const venvPython = path.join(ROOT_DIR, "agent/.venv/bin/python3");
  const managerScript = path.join(ROOT_DIR, "scripts/manager.py");
  try {
    const proc = Bun.spawn([venvPython, managerScript], {
      cwd: ROOT_DIR,
      stdout: "ignore",
      stderr: "ignore",
      stdin: "ignore"
    });
    proc.unref();
  } catch (e) {
    console.error("Failed to auto-start manager", e);
  }
}

// ── Types ──────────────────────────────────────────────────────────────────
interface ApiRecord {
  id: string;
  url: string;
  schema: string;
  port: number;
  status: "generating" | "running" | "failed" | "stopped";
  created_at: string;
  error?: string | null;
}

type ViewName = "LIST" | "NEW_API" | "GENERATING" | "DATA";

// ── Helpers ────────────────────────────────────────────────────────────────
function statusColor(status: string) {
  if (status === "running") return "green";
  if (status === "generating") return "yellow";
  if (status === "failed") return "red";
  return "dim";
}

function statusIcon(status: string) {
  if (status === "running") return "✓";
  if (status === "generating") return "⟳";
  if (status === "failed") return "✗";
  return "○";
}

function timeAgo(iso: string) {
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}

// ── Main App ───────────────────────────────────────────────────────────────
function App() {
  const [view, setView] = useState<ViewName>("LIST");
  const [apis, setApis] = useState<ApiRecord[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [managerOnline, setManagerOnline] = useState(false);

  // New API form
  const [newUrl, setNewUrl] = useState("");
  const [newSchema, setNewSchema] = useState("");
  const [formFocus, setFormFocus] = useState(0); // 0=url 1=schema 2=button

  // Generation state
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [genLogs, setGenLogs] = useState<string[]>([]);
  const genPollRef = useRef<any>(null);

  // Data view
  const [dataApiId, setDataApiId] = useState<string | null>(null);
  const [dataItems, setDataItems] = useState<any[]>([]);
  const [dataLoading, setDataLoading] = useState(false);

  // ── Fetch API list ────────────────────────────────────────────────────
  const fetchApis = async () => {
    try {
      const r = await fetch(`${MANAGER_URL}/apis`);
      if (r.ok) {
        const data = await r.json();
        setApis(data);
        setManagerOnline(true);
      }
    } catch {
      setManagerOnline(false);
    }
  };

  // Poll list every 3s
  useEffect(() => {
    // Try reaching Manager; if offline, auto-start it
    fetch(MANAGER_URL + "/").catch(() => {
      ensureManagerRunning();
    });
    fetchApis();
    const interval = setInterval(fetchApis, 3000);
    return () => clearInterval(interval);
  }, []);

  // ── Poll generation logs ──────────────────────────────────────────────
  const startLogPolling = (apiId: string) => {
    if (genPollRef.current) clearInterval(genPollRef.current);
    genPollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${MANAGER_URL}/apis/${apiId}/logs/all`);
        if (r.ok) {
          const { logs } = await r.json();
          setGenLogs(logs);

          // Check status
          const sr = await fetch(`${MANAGER_URL}/apis/${apiId}/status`);
          if (sr.ok) {
            const status: ApiRecord = await sr.json();
            if (status.status === "running") {
              clearInterval(genPollRef.current!);
              setGeneratingId(null);
              setView("LIST");
              fetchApis();
            } else if (status.status === "failed") {
              clearInterval(genPollRef.current!);
              setGenLogs(prev => [...prev, `[!] FAILED: ${status.error || "Unknown error"}`]);
            }
          }
        }
      } catch { }
    }, 1500);
  };

  // ── Fetch data for selected API ───────────────────────────────────────
  const fetchApiData = async (apiId: string) => {
    setDataLoading(true);
    setDataItems([]);
    try {
      const r = await fetch(`${MANAGER_URL}/apis/${apiId}/data`);
      if (r.ok) {
        const data = await r.json();
        setDataItems(Array.isArray(data) ? data : [data]);
      } else {
        const err = await r.json();
        setDataItems([{ error: err.detail }]);
      }
    } catch (e: any) {
      setDataItems([{ error: e.message }]);
    }
    setDataLoading(false);
  };

  // ── Generate new API ──────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (!newUrl) return;
    setGenLogs(["[+] Sending request to Weaver Manager..."]);
    setView("GENERATING");

    try {
      const r = await fetch(`${MANAGER_URL}/apis/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: newUrl, schema: newSchema }),
      });

      if (r.ok) {
        const api: ApiRecord = await r.json();
        setGeneratingId(api.id);
        setGenLogs(prev => [...prev, `[+] API ID: ${api.id}`, `[+] Port: ${api.port}`]);
        startLogPolling(api.id);
        setNewUrl("");
        setNewSchema("");
      } else {
        setGenLogs(prev => [...prev, "[!] Manager rejected request. Is the Manager running?"]);
      }
    } catch {
      setGenLogs(prev => [...prev, "[!] Cannot reach Manager. Run: python scripts/manager.py"]);
    }
  };

  // ── Delete API ─────────────────────────────────────────────────────────
  const handleDelete = async () => {
    const api = apis[selectedIndex];
    if (!api) return;
    await fetch(`${MANAGER_URL}/apis/${api.id}`, { method: "DELETE" });
    fetchApis();
  };

  // ── Keyboard ──────────────────────────────────────────────────────────
  useKeyboard((key) => {
    if (view === "LIST") {
      if (key.name === "up" || key.name === "k") setSelectedIndex(i => Math.max(0, i - 1));
      if (key.name === "down" || key.name === "j") setSelectedIndex(i => Math.min(apis.length - 1, i + 1));
      if (key.name === "n") { setView("NEW_API"); setFormFocus(0); }
      if (key.name === "d") handleDelete();
      if (key.name === "enter" || key.name === "return") {
        const api = apis[selectedIndex];
        if (api?.status === "running") {
          setDataApiId(api.id);
          setView("DATA");
          fetchApiData(api.id);
        }
      }
      if (key.name === "r") fetchApis();
    }

    if (view === "NEW_API") {
      if (key.name === "tab") setFormFocus(f => (f + 1) % 3);
      if ((key.name === "enter" || key.name === "return") && formFocus === 2) handleGenerate();
      if (key.name === "escape") setView("LIST");
    }

    if (view === "GENERATING") {
      if (key.name === "escape") {
        if (genPollRef.current) clearInterval(genPollRef.current);
        setView("LIST");
      }
    }

    if (view === "DATA") {
      if (key.name === "escape") setView("LIST");
      if (key.name === "r") fetchApiData(dataApiId!);
    }
  });

  // ── Render: Header ────────────────────────────────────────────────────
  const Header = (
    <box flexDirection="row" justifyContent="space-between" alignItems="center" border borderStyle="rounded" borderColor="cyan" paddingX={2} height={3} marginBottom={1}>
      <text fg="cyan" attributes={TextAttributes.BOLD}>⬡ WEAVER — Agentic Data Service</text>
      <box flexDirection="row" gap={2}>
        <text fg="dim">[ </text>
        <text fg={view === "LIST" ? "white" : "dim"} attributes={view === "LIST" ? TextAttributes.BOLD : TextAttributes.NONE}>LIST</text>
        <text fg="dim"> | </text>
        <text fg={view === "NEW_API" ? "white" : "dim"} attributes={view === "NEW_API" ? TextAttributes.BOLD : TextAttributes.NONE}>NEW API</text>
        <text fg="dim"> | </text>
        <text fg={view === "DATA" ? "white" : "dim"} attributes={view === "DATA" ? TextAttributes.BOLD : TextAttributes.NONE}>DATA</text>
        <text fg="dim"> ]</text>
      </box>
      <box flexDirection="row" gap={1}>
        <text fg={managerOnline ? "green" : "red"}>{managerOnline ? "●" : "○"}</text>
        <text fg={managerOnline ? "green" : "red"} attributes={TextAttributes.DIM}>{managerOnline ? "Manager Online" : "Manager Offline"}</text>
      </box>
    </box>
  );

  // ── Render: LIST View ─────────────────────────────────────────────────
  const renderList = () => (
    <box flexDirection="column" flexGrow={1}>
      <scrollbox flexGrow={1} border borderStyle="single" borderColor="dim" title={` ${apis.length} Active API${apis.length !== 1 ? "s" : ""} `} focused>
        {apis.length === 0 ? (
          <box flexGrow={1} alignItems="center" justifyContent="center" flexDirection="column">
            <text fg="dim">No APIs yet. Press N to create one.</text>
          </box>
        ) : (
          apis.map((api, i) => {
            const isSelected = i === selectedIndex;
            return (
              <box
                key={api.id}
                flexDirection="row"
                paddingX={2}
                paddingY={0.5}
                backgroundColor={isSelected ? "#1a1a2e" : "transparent"}
                border={isSelected ? ["left"] : undefined}
                borderColor="cyan"
              >
                <box width={4}>
                  <text fg={statusColor(api.status)} attributes={TextAttributes.BOLD}>
                    {statusIcon(api.status)}
                  </text>
                </box>
                <box flexGrow={1} flexDirection="column">
                  <text fg={isSelected ? "white" : "dim"} attributes={isSelected ? TextAttributes.BOLD : TextAttributes.NONE}>
                    {api.url}
                  </text>
                  <text fg="dim" attributes={TextAttributes.DIM}>{api.schema.slice(0, 60)}...</text>
                </box>
                <box flexDirection="column" alignItems="flex-end" gap={0}>
                  <text fg={statusColor(api.status)} attributes={TextAttributes.BOLD}>{api.status.toUpperCase()}</text>
                  <text fg="dim" attributes={TextAttributes.DIM}>:{api.port}  {timeAgo(api.created_at)}</text>
                </box>
              </box>
            );
          })
        )}
      </scrollbox>
      <box height={1} marginTop={1} paddingX={1} justifyContent="space-between">
        <text fg="dim">↑↓: Select | ENTER: View Data | D: Delete | N: New API</text>
        <text fg="dim">R: Refresh</text>
      </box>
    </box>
  );

  // ── Render: NEW API View ──────────────────────────────────────────────
  const renderNewApi = () => (
    <box flexDirection="column" flexGrow={1} gap={1}>
      <box flexDirection="column" border borderStyle="single" borderColor={formFocus === 0 ? "yellow" : "dim"} padding={1} title=" Target URL ">
        <input
          value={newUrl}
          // @ts-ignore
          onChange={setNewUrl}
          focused={formFocus === 0}
          placeholder="https://example.com"
          textColor={formFocus === 0 ? "white" : "dim"}
        />
      </box>

      <box flexDirection="column" border borderStyle="single" borderColor={formFocus === 1 ? "yellow" : "dim"} padding={1} title=" Data Schema ">
        <textarea
          initialValue={newSchema}
          // @ts-ignore
          onChange={setNewSchema}
          focused={formFocus === 1}
          height={5}
          placeholder="Describe what data to extract (e.g. article titles, authors, dates)..."
        />
      </box>

      <box
        border
        borderStyle="rounded"
        borderColor={formFocus === 2 ? "green" : "dim"}
        paddingY={1}
        height={3}
        alignItems="center"
        justifyContent="center"
        backgroundColor={formFocus === 2 ? "#0d2b0d" : "transparent"}
      >
        <text fg={formFocus === 2 ? "green" : "dim"} attributes={formFocus === 2 ? TextAttributes.BOLD : TextAttributes.DIM}>
          {formFocus === 2 ? "▶  Generate API Now  ◀" : "[ Generate API ]"}
        </text>
      </box>

      <box height={1} marginTop={1} paddingX={1} justifyContent="center">
        <text fg="dim">TAB: Switch fields | ENTER on ▶ button: Generate | ESC: Back</text>
      </box>
    </box>
  );

  // ── Render: GENERATING View ───────────────────────────────────────────
  const renderGenerating = () => {
    const has = (s: string) => genLogs.some(l => l.includes(s));
    const hasErr = genLogs.some(l => l.startsWith("[!]") && !l.includes("Waiting"));

    const phases = [
      { label: "⬡ Agent: Launch Browser",    sub: "Opening real Chromium, navigating to target URL",                   done: has("browser_navigate") || has("BROWSE"), active: has("Hermes Agent is opening") && !has("browser_navigate") },
      { label: "⬡ Agent: Wait for JS",       sub: "Waiting for SPA/JS content and lazy-loaded items to fully render", done: has("ANALYZE") || has("browser_scroll"),                active: has("browser_navigate") && !has("ANALYZE") },
      { label: "⬡ Agent: Extract Data",      sub: "Identifying CSS selectors/JSON keys matching your schema",          done: has("WRITE THE SCRAPER") || has("write_file"),          active: has("ANALYZE") && !has("write_file") },
      { label: "⬡ Agent: Write FastAPI Code",sub: "Generating scraper_generated.py with Playwright and CORS",          done: has("VERIFY") || has("import scraper"),                 active: has("write_file") && !has("VERIFY") },
      { label: "Starting Server",            sub: "Launching uvicorn, polling until first successful HTTP response",    done: has("API is LIVE"),                                     active: has("GENERATION_COMPLETE") && !has("API is LIVE") },
    ];

    const recentLogs = genLogs.slice(-6);

    return (
      <box flexDirection="column" flexGrow={1} gap={1}>
        <box flexDirection="column" border borderStyle="double" borderColor={hasErr ? "red" : "yellow"} padding={1} title={hasErr ? " ✗ Generation Failed " : " ⟳ Generation Progress "}>
          {phases.map((phase, i) => {
            const color = phase.done ? "green" : phase.active ? "yellow" : "dim";
            const icon  = phase.done ? "✓" : phase.active ? "▶" : "○";
            const attr  = phase.active ? TextAttributes.BOLD : TextAttributes.NONE;
            return (
              <box key={i} flexDirection="row" paddingY={0.5} paddingX={1}>
                <box width={3}><text fg={color} attributes={TextAttributes.BOLD}>{icon}</text></box>
                <box flexDirection="column" flexGrow={1}>
                  <text fg={color} attributes={attr}>Step {i + 1}: {phase.label}</text>
                  <text fg="dim" attributes={TextAttributes.DIM}>{phase.sub}</text>
                </box>
              </box>
            );
          })}
        </box>

        <box flexDirection="column" border borderStyle="single" borderColor="dim" padding={1} flexGrow={1} title=" Live Output ">
          {recentLogs.length === 0
            ? <text fg="dim">Starting...</text>
            : recentLogs.map((log, i) => (
                <text key={i} fg={log.startsWith("[!]") ? "red" : log.startsWith("[✓]") || log.startsWith("[v]") ? "green" : log.startsWith("[+]") ? "cyan" : log.startsWith("[~]") ? "yellow" : "dim"}>
                  {log.slice(0, 140)}
                </text>
              ))
          }
        </box>

        <box height={1} paddingX={1}>
          <text fg="dim">ESC: Back to List  (generation continues in background)</text>
        </box>
      </box>
    );
  };

  // ── Render: DATA View ─────────────────────────────────────────────────
  const renderData = () => {
    const api = apis.find(a => a.id === dataApiId);
    return (
      <box flexDirection="column" flexGrow={1}>
        <box height={2} paddingX={1} marginBottom={1} flexDirection="column">
          <text fg="green" attributes={TextAttributes.BOLD}>● {api?.url}</text>
          <text fg="dim" attributes={TextAttributes.DIM}>Port {api?.port} | Schema: {api?.schema.slice(0, 80)}</text>
        </box>

        <scrollbox flexGrow={1} border borderStyle="single" borderColor="cyan" focused>
          {dataLoading ? (
            <box flexGrow={1} alignItems="center" justifyContent="center">
              <text fg="yellow">⌛ Fetching data from API...</text>
            </box>
          ) : dataItems.length === 0 ? (
            <box flexGrow={1} alignItems="center" justifyContent="center">
              <text fg="dim">No data returned.</text>
            </box>
          ) : dataItems[0]?.error ? (
            <box flexGrow={1} alignItems="center" justifyContent="center" padding={2}>
              <text fg="red">{dataItems[0].error}</text>
            </box>
          ) : (
            dataItems.map((item, index) => (
              <box key={index} flexDirection="column" paddingY={0.5} paddingX={1} border={["bottom"]} borderColor="dim">
                <text fg="yellow" attributes={TextAttributes.BOLD}>{index + 1}.</text>
                <text fg="cyan">{JSON.stringify(item, null, 2)}</text>
              </box>
            ))
          )}
        </scrollbox>
        <box height={1} marginTop={1} paddingX={1} justifyContent="space-between">
          <text fg="dim">R: Refresh Data</text>
          <text fg="dim">ESC: Back to List</text>
        </box>
      </box>
    );
  };

  // ── Root Render ───────────────────────────────────────────────────────
  return (
    <box flexDirection="column" flexGrow={1} padding={1} backgroundColor="#080812">
      {Header}
      <box flexDirection="column" flexGrow={1}>
        {view === "LIST" && renderList()}
        {view === "NEW_API" && renderNewApi()}
        {view === "GENERATING" && renderGenerating()}
        {view === "DATA" && renderData()}
      </box>
      <box height={1} marginTop={1} paddingX={1}>
        <text fg="cyan" attributes={TextAttributes.DIM}>⬡ Weaver v1.2  </text>
        <text fg="dim">|  Nous Hermes 4-405B  |  </text>
        <text fg="dim">Manager: {MANAGER_URL}</text>
      </box>
    </box>
  );
}

const renderer = await createCliRenderer();
createRoot(renderer).render(<App />);
