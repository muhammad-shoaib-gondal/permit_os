import { useState } from "react";

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitted(true);
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <span className="auth-logo-icon">⚡</span>
          <span className="auth-logo-name">PermitOS</span>
        </div>
        <h1 className="auth-title">Create account</h1>
        <p className="auth-subtitle">Get started with PermitOS</p>

        {submitted ? (
          <div className="auth-success">
            <p>Thanks for your interest! We'll be in touch soon.</p>
            <a href="/app/" className="auth-btn" style={{ display: "block", textAlign: "center", marginTop: "1rem" }}>
              Back to login
            </a>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form">
            <div className="auth-field">
              <label htmlFor="name">Full name</label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                required
              />
            </div>
            <div className="auth-field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
              />
            </div>
            <div className="auth-field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a password"
                required
              />
            </div>
            <button type="submit" className="auth-btn">
              Create account
            </button>
          </form>
        )}

        <p className="auth-footer">
          Already have an account?{" "}
          <a href="/app/">Sign in</a>
        </p>
      </div>
    </div>
  );
}
