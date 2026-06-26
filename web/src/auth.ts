const SESSION_KEY = "permitos_auth";

export function isAuthenticated(): boolean {
  return sessionStorage.getItem(SESSION_KEY) === "true";
}

export function login(username: string, password: string): boolean {
  if (username === "admin" && password === "admin") {
    sessionStorage.setItem(SESSION_KEY, "true");
    return true;
  }
  return false;
}

export function logout(): void {
  sessionStorage.removeItem(SESSION_KEY);
}
