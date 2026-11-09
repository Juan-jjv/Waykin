import type { CSSProperties } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { nav } from "../copy/familyStrings";
import { useAccount } from "../family/api";

/** Which tab a path belongs to, in link order; -1 for screens outside the four tabs. */
export function tabIndex(pathname: string): number {
  if (pathname === "/") return 0;
  if (pathname.startsWith("/family")) return 1;
  if (pathname.startsWith("/history")) return 2;
  if (pathname.startsWith("/account") || pathname.startsWith("/login") || pathname.startsWith("/signup")) return 3;
  return -1;
}

export function NavBar() {
  const account = useAccount();
  const { pathname } = useLocation();
  const active = tabIndex(pathname);
  const cls = ({ isActive }: { isActive: boolean }) => (isActive ? "nav-link active" : "nav-link");
  return (
    <nav className="nav" aria-label="Main" style={{ "--active": active } as CSSProperties}>
      {active >= 0 ? <span className="nav-thumb" aria-hidden="true" /> : null}
      <NavLink to="/" end className={cls}>{nav.plan}</NavLink>
      <NavLink to="/family" className={cls}>{nav.family}</NavLink>
      <NavLink to="/history" className={cls}>{nav.history}</NavLink>
      <NavLink to={account.data ? "/account" : "/login"} className={cls}>
        {account.data ? nav.account : nav.signIn}
      </NavLink>
    </nav>
  );
}
