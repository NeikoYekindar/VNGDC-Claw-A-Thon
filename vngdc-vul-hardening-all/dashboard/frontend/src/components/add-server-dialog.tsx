"use client";
import { useState } from "react";
import { api, type ServerCreate } from "@/lib/api";

interface Props {
  onAdded: () => void;
}

export function AddServerDialog({ onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [authMode, setAuthMode] = useState<"password" | "key">("password");
  const [form, setForm] = useState<ServerCreate>({
    name: "", host: "", port: 22, username: "root", os_type: "ubuntu", password: "", ssh_key: "",
  });

  const set = (k: keyof ServerCreate, v: string | number) =>
    setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload: ServerCreate = { ...form };
      if (authMode === "password") delete payload.ssh_key;
      else delete payload.password;
      await api.createServer(payload);
      setOpen(false);
      setForm({ name: "", host: "", port: 22, username: "root", os_type: "ubuntu", password: "", ssh_key: "" });
      onAdded();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        Add Server
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-slate-950/35 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <div className="relative mx-4 w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold">Add New Server</h2>
              <button onClick={() => setOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={submit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs text-muted-foreground mb-1.5 font-medium">Server Name</label>
                  <input value={form.name} onChange={(e) => set("name", e.target.value)} required
                    placeholder="web-server-01"
                    className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-xs text-muted-foreground mb-1.5 font-medium">OS Type</label>
                  <select value={form.os_type} onChange={(e) => set("os_type", e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary">
                    <option value="ubuntu">Ubuntu 24.04</option>
                    <option value="windows">Windows Server 2022</option>
                    <option value="junos">Juniper Junos Switch</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="block text-xs text-muted-foreground mb-1.5 font-medium">IP / Hostname</label>
                  <input value={form.host} onChange={(e) => set("host", e.target.value)} required
                    placeholder="192.168.1.10"
                    className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                </div>
                <div>
                  <label className="block text-xs text-muted-foreground mb-1.5 font-medium">Port</label>
                  <input type="number" value={form.port} onChange={(e) => set("port", parseInt(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                </div>
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1.5 font-medium">SSH Username</label>
                <input value={form.username} onChange={(e) => set("username", e.target.value)} required
                  placeholder="root"
                  className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
              </div>

              {/* Auth toggle */}
              <div>
                <div className="flex gap-2 mb-3">
                  {(["password", "key"] as const).map((m) => (
                    <button key={m} type="button" onClick={() => setAuthMode(m)}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${authMode === m ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"}`}>
                      {m === "password" ? "Password" : "SSH Key"}
                    </button>
                  ))}
                </div>
                {authMode === "password" ? (
                  <input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} required
                    placeholder="SSH password"
                    className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-sm focus:outline-none focus:ring-1 focus:ring-primary" />
                ) : (
                  <textarea value={form.ssh_key} onChange={(e) => set("ssh_key", e.target.value)} required
                    rows={4} placeholder="-----BEGIN RSA PRIVATE KEY-----..."
                    className="w-full px-3 py-2 rounded-lg bg-secondary border border-border text-sm font-mono focus:outline-none focus:ring-1 focus:ring-primary resize-none" />
                )}
              </div>

              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {error}
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setOpen(false)}
                  className="flex-1 px-4 py-2 rounded-lg border border-border text-sm hover:bg-secondary transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={loading}
                  className="flex-1 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors">
                  {loading ? "Adding..." : "Add Server"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
