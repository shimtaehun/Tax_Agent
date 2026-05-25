"use client";

import { useState, FormEvent } from "react";
import { login } from "../../lib/api";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      window.location.href = "/";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "로그인 실패");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="loginWrap">
      <div className="loginCard">
        <div className="brand">Tax-Copilot</div>
        <p className="loginSub">세무사를 위한 AI 영수증 검토 시스템</p>
        <form onSubmit={handleSubmit}>
          <label>
            이메일
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tax@example.com"
              required
            />
          </label>
          <label>
            비밀번호
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </label>
          {error && <p className="errMsg">{error}</p>}
          <button type="submit" disabled={loading} className="loginBtn">
            {loading ? "로그인 중..." : "로그인"}
          </button>
        </form>
        <p className="loginHint">데모 계정: admin@example.com / password</p>
      </div>
    </main>
  );
}
