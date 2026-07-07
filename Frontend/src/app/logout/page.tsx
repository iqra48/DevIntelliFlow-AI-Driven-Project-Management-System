"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { signOut } from "firebase/auth";
import { auth } from '@/firebase/firebaseConfig'; 

export default function LogoutPage() {
  const router = useRouter();

  useEffect(() => {
    const doLogout = async () => {
      try {
        await signOut(auth);
        router.push("/login"); // redirect after logout
      } catch (error) {
        console.error("Logout error:", error);
      }
    };
    doLogout();
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="bg-white p-8 rounded-2xl shadow-md text-center">
        <h1 className="text-xl font-semibold text-gray-800">
          Logging you out...
        </h1>
        <p className="text-gray-500 text-sm mt-2">Please wait</p>
      </div>
    </div>
  );
}
