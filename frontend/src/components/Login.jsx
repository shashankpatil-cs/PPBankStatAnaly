import React, { useState } from "react";
import { login, signup } from "../api.js";

export default function Login() {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = mode === "login" ? await login(email, password) : await signup(email, password, name);
      localStorage.setItem("access_token", res.data.access_token);
      window.location.href = "/";
    } catch (err) {
      setError(err.response?.data?.detail || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="center-page">
      <div className="card auth-card">
        <h2>{mode === "login" ? "Log in" : "Create account"}</h2>
        <form onSubmit={submit}>
          {mode === "signup" && (
            <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && <div className="error-text">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? "Please wait..." : mode === "login" ? "Log in" : "Sign up"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 14 }}>
          {mode === "login" ? "No account yet?" : "Already have an account?"}{" "}
          <a href="#" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
            {mode === "login" ? "Sign up" : "Log in"}
          </a>
        </p>
      </div>
    </div>
  );
}
