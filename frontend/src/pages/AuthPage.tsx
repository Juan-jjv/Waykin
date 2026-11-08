import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { NavBar } from "../components/NavBar";
import { authText } from "../copy/familyStrings";
import { accountApi } from "../family/api";

/** Only same-site paths are allowed as the post-login destination. */
function safeNext(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/family";
}

export function AuthPage({ mode }: { mode: "in" | "up" }) {
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [name, setName] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const account = mode === "up"
        ? await accountApi.signUp(name.trim(), login.trim(), password)
        : await accountApi.logIn(login.trim(), password);
      qc.setQueryData(["account"], account);
      await qc.invalidateQueries({ queryKey: ["families"] });
      navigate(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const other = mode === "up" ? "/login" : "/signup";
  return (
    <div className="page">
      <NavBar />
      <form className="page-card form" onSubmit={(e) => void submit(e)}>
        <h1>{mode === "up" ? authText.signUpTitle : authText.signInTitle}</h1>
        {mode === "up" ? (
          <label>
            {authText.name}
            <input required maxLength={40} autoComplete="nickname" value={name} onChange={(e) => setName(e.target.value)} />
            <small className="hint">{authText.nameHint}</small>
          </label>
        ) : null}
        <label>
          {authText.login}
          <input required minLength={3} maxLength={80} autoComplete="username" value={login} onChange={(e) => setLogin(e.target.value)} />
        </label>
        <label>
          {authText.password}
          <input required type="password" minLength={mode === "up" ? 10 : 1} maxLength={200}
            autoComplete={mode === "up" ? "new-password" : "current-password"} value={password}
            onChange={(e) => setPassword(e.target.value)} />
          {mode === "up" ? <small className="hint">{authText.passwordHint}</small> : null}
        </label>
        {error ? <p className="notice">{error}</p> : null}
        <button type="submit" className="btn-primary find" disabled={busy}>
          {mode === "up" ? authText.submitUp : authText.submitIn}
        </button>
        <Link to={`${other}?next=${encodeURIComponent(next)}`} className="hint">{mode === "up" ? authText.toIn : authText.toUp}</Link>
        {mode === "up" ? <p className="hint">{authText.privacy}</p> : null}
      </form>
    </div>
  );
}
