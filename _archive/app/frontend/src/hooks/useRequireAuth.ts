import { useAuth } from "@/contexts/AuthContext";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/**
 * Require an authenticated beta account for app pages.
 */
export function useRequireAuth() {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!loading && !user) {
      navigate("/login", { replace: true, state: { from: `${location.pathname}${location.search}` } });
    }
  }, [loading, location.pathname, location.search, navigate, user]);

  return { user, loading, isAuthenticated: !!user };
}
