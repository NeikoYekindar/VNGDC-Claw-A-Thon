"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const securityNavItems = [
  {
    href: "/",
    label: "Hardening",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3l7 3v5c0 4.4-2.9 8.4-7 9.7-4.1-1.3-7-5.3-7-9.7V6l7-3z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-5" />
      </svg>
    ),
  },
  {
    href: "/vulnerabilities",
    label: "Vul Assets",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v4m0 4h.01M10.3 4.4L2.8 18a2 2 0 001.7 3h15a2 2 0 001.7-3L13.7 4.4a2 2 0 00-3.4 0z" />
      </svg>
    ),
  },
  {
    href: "/vulnerabilities/radar",
    label: "CVE Radar",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12h3l2.3-6 4.4 12L15 12h6" />
      </svg>
    ),
  },
];

const mainNavItems = [
  {
    href: "/chat",
    label: "Agent Chat",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h8M8 14h5m8-2a8 8 0 11-15.5-2.8L3 21l4.2-1.4A8 8 0 0021 12z" />
      </svg>
    ),
  },
];

const securityIcon = (
  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3l7 3v5c0 4.4-2.9 8.4-7 9.7-4.1-1.3-7-5.3-7-9.7V6l7-3z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-5" />
  </svg>
);

const chevronIcon = (
  <svg className="h-3.5 w-3.5 transition-transform group-hover:rotate-180 group-focus-within:rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 9l6 6 6-6" />
  </svg>
);

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/" || pathname.startsWith("/server");
  if (href === "/vulnerabilities") {
    return pathname === href || (pathname.startsWith("/vulnerabilities/") && !pathname.startsWith("/vulnerabilities/radar"));
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const securityActive = securityNavItems.some((item) => isActive(pathname, item.href));

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-52 border-b border-blue-100 bg-[linear-gradient(180deg,#eff6ff_0%,rgba(239,246,255,0)_100%)]" />
      <header className="sticky top-0 z-40 border-b border-border bg-card/95 backdrop-blur">
        <div className="flex min-h-16 w-full flex-col gap-3 px-5 py-3 sm:px-8 2xl:px-10 md:flex-row md:items-center md:gap-6">
          <Link href="/" className="flex min-w-fit items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-blue-200 bg-blue-50 text-primary">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3l7 3v5c0 4.4-2.9 8.4-7 9.7-4.1-1.3-7-5.3-7-9.7V6l7-3z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold leading-5 tracking-tight">VNGDC Security</p>
              <p className="text-xs text-muted-foreground">Hardening and vulnerability operations</p>
            </div>
          </Link>

          <nav className="flex w-full items-center gap-2 overflow-visible md:justify-end">
            <div className="group relative shrink-0">
              <button
                type="button"
                className={cn(
                  "inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-sm font-medium transition-colors",
                  securityActive
                    ? "border-blue-200 bg-blue-50 text-primary"
                    : "border-transparent text-muted-foreground hover:border-border hover:bg-secondary hover:text-foreground",
                )}
              >
                {securityIcon}
                Security
                {chevronIcon}
              </button>
              <div className="invisible absolute right-0 top-[calc(100%+0.5rem)] z-50 min-w-56 translate-y-1 rounded-lg border border-border bg-card p-1.5 opacity-0 shadow-lg transition-all group-hover:visible group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:visible group-focus-within:translate-y-0 group-focus-within:opacity-100">
                {securityNavItems.map((item) => {
                  const active = isActive(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex h-10 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors",
                        active
                          ? "bg-blue-50 text-primary"
                          : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                      )}
                    >
                      {item.icon}
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>

            {mainNavItems.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "inline-flex h-9 shrink-0 items-center gap-2 rounded-lg border px-3 text-sm font-medium transition-colors",
                    active
                      ? "border-blue-200 bg-blue-50 text-primary"
                      : "border-transparent text-muted-foreground hover:border-border hover:bg-secondary hover:text-foreground",
                  )}
                >
                  {item.icon}
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="w-full px-5 py-6 sm:px-8 2xl:px-10">{children}</main>
    </div>
  );
}
