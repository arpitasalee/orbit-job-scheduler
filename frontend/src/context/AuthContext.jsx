import { createContext, useContext, useEffect, useState } from "react";
import { api, setToken } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const { access_token } = await api.login({ email, password });
    setToken(access_token);
    setUser(await api.me());
  }

  async function register(orgName, email, password) {
    const { access_token } = await api.register({ org_name: orgName, email, password });
    setToken(access_token);
    setUser(await api.me());
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
