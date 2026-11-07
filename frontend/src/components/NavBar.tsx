import { NavLink } from "react-router-dom";
import { nav } from "../copy/familyStrings";
import { useAccount } from "../family/api";

export function NavBar() {
  const account = useAccount();
  const cls = ({ isActive }: { isActive: boolean }) => (isActive ? "nav-link active" : "nav-link");
  return (
    <nav className="nav" aria-label="Main">
      <NavLink to="/" end className={cls}>{nav.plan}</NavLink>
      <NavLink to="/family" className={cls}>{nav.family}</NavLink>
      <NavLink to="/history" className={cls}>{nav.history}</NavLink>
      <NavLink to={account.data ? "/account" : "/login"} className={cls}>
        {account.data ? nav.account : nav.signIn}
      </NavLink>
    </nav>
  );
}
