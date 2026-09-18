"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Projects", match: (path: string) => path === "/" || path.startsWith("/projects") },
  { href: "/system", label: "System", match: (path: string) => path.startsWith("/system") },
  {
    href: "/about-developer",
    label: "About the developer",
    match: (path: string) => path.startsWith("/about-developer"),
  },
];

/** The mark: a coverage bar in miniature, one line still waiting for its image. */
export function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden focusable="false">
      <rect x="1" y="1" width="30" height="30" rx="6" fill="#242A31" stroke="#343B44" strokeWidth="2" />
      <rect x="6" y="11" width="6" height="10" fill="#E6E8EB" />
      <rect x="13" y="11" width="4" height="10" fill="#4FB286" />
      <rect x="18" y="11" width="3" height="10" fill="#E0A23A" />
      <rect x="22" y="11" width="4" height="10" fill="#E6E8EB" />
    </svg>
  );
}

export function SiteHeader() {
  const pathname = usePathname() || "/";
  return (
    <header className="border-b border-hairline">
      <div className="mx-auto flex w-full max-w-[1400px] flex-wrap items-center gap-x-8 gap-y-1 px-4 py-2 sm:px-6 lg:px-8">
        <Link href="/" className="flex h-10 items-center gap-2 rounded-[var(--radius-control)]">
          <Mark />
          <span className="heading text-xl leading-none">img2vid</span>
        </Link>
        <nav aria-label="Main">
          <ul className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm">
            {links.map((link) => {
              const active = link.match(pathname);
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    className={`inline-flex h-10 items-center border-b-2 ${
                      active ? "border-text text-text" : "border-transparent text-muted hover:text-text"
                    }`}
                  >
                    {link.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
