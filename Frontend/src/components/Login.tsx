"use client";

import React, { useState } from "react";
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "@/firebase/firebaseConfig";
import { useRouter } from "next/navigation";
import { signInWithGoogle } from "@/firebase/Signin";
import Image from "next/image";

export default function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  // ✅ Handle email/password login
  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    try {
      await auth.signOut();
      await signInWithEmailAndPassword(auth, email, password);
      router.push("/dashboard");
    } catch (error: unknown) {
      if (error && typeof error === "object" && "code" in error && "message" in error) {
        const errCode = (error as { code: string; message: string }).code;
        switch (errCode) {
          case "auth/user-not-found":
            setError("Email is not registered.");
            break;
          case "auth/wrong-password":
            setError("Incorrect password.");
            break;
          case "auth/too-many-requests":
            setError("Too many login attempts. Please try again later.");
            break;
          default:
            console.error("Unhandled Firebase Auth Error:", errCode, (error as { message: string }).message);
            setError("Login failed: " + (error as { message: string }).message);
        }
      } else {
        setError("An unknown error occurred.");
        console.error("Unexpected error:", error);
      }
    }
  };

  // ✅ Handle Google sign-in
  const handleGoogleSignIn = async () => {
    try {
      const user = await signInWithGoogle();
      console.log("Signed in:", user.displayName);
      router.push("/dashboard");
    } catch (error) {
      console.error("Google sign-in error:", error);
      setError("Google authentication failed!");
    }
  };

  return (
    <div className="md:w-1/2 flex items-center justify-center p-8 bg-green-600 rounded-l-4xl">
      <div className="w-full max-w-md text-center bg-white/90 backdrop-blur-sm p-6 rounded-lg shadow-md">
        <h2 className="text-4xl font-extrabold mb-2 text-black">Welcome Back</h2>
        <h4 className="text-base text-gray-500 mb-6">
          Don&apos;t have an account?{" "}
          <a href="/signup" className="text-purple-700 font-bold hover:underline">
            Sign Up
          </a>
        </h4>

        <form onSubmit={handleEmailLogin} className="space-y-4 text-left">
          <div>
            <label className="block text-gray-600 font-bold">E-mail</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
              className="w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400 text-gray-500"
            />
          </div>
          <div>
            <label className="block text-gray-600 font-bold">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              className="w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400 text-gray-500"
            />
          </div>

          <div>
            <a href="/forgot-password" className="text-blue-700 hover:underline">
              Forgot Password?
            </a>
          </div>

          {error && <div className="text-red-600 font-medium">{error}</div>}

          <div className="mt-4">
            <button
              type="submit"
              className="bg-gradient-to-r from-purple-700 via-blue-800 to-blue-900 text-white px-6 py-2 rounded-md font-semibold w-full hover:opacity-90 transition"
            >
              Sign In
            </button>
          </div>
        </form>

        <div className="mt-6">
          <button
            onClick={handleGoogleSignIn}
            className="flex items-center justify-center w-full bg-white border text-gray-700 font-semibold py-2 rounded-md shadow hover:shadow-md transition"
          >
            <Image
              src="https://www.svgrepo.com/show/475656/google-color.svg"
              width={24}
              height={24}
              className="mr-2"
              alt="Google"
            />
            Sign in with Google
          </button>
        </div>
      </div>
    </div>
  );
}
