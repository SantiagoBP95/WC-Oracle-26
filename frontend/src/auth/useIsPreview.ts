import { useAuth } from "./AuthContext";

/** Devuelve true si el usuario está en el perfil "preview" (acceso limitado). */
export function useIsPreview(): boolean {
  const { user } = useAuth();
  return user?.profile?.toLowerCase() === "preview";
}
