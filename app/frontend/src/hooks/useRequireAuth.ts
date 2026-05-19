import { useAuth } from "@/contexts/AuthContext";

/**
 * Hook that previously required authentication and redirected to /login.
 * Now it simply returns the current auth state without enforcing login.
 * Pages will work for both authenticated and guest users.
 */
export function useRequireAuth() {
  const { user, loading } = useAuth();

  // No redirect — allow guest access
  return { user, loading, isAuthenticated: !!user };
}