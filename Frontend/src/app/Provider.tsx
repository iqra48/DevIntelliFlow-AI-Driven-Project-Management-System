"use client";

import { AuthProvider } from "@/context/AuthContext";

export function Provider({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
