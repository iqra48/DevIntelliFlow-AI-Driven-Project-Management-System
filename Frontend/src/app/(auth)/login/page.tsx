"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "@/firebase/firebaseConfig";
import { signInWithGoogle } from "@/firebase/Signin";
import Image from "next/image";
import { motion } from "@/lib/motion";


export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await auth.signOut();
      await signInWithEmailAndPassword(auth, email, password);
      router.push("/dashboard");
    } catch (error: any) {
      switch (error.code) {
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
          console.error(error);
          setError("Login failed. Please try again.");
      }
    }
  };

  const handleGoogleSignIn = async () => {
    try {
      const user = await signInWithGoogle();
      console.log("Signed in:", user.displayName);
      router.push("/dashboard");
    } catch {
      setError("Google authentication failed!");
    }
  };

 return (
  <motion.div
  initial={{ opacity: 0, scale: 0.95 }}
  animate={{ opacity: 1, scale: 1 }}
  transition={{ duration: 0.5, ease: "easeOut" }}
  className="w-full max-w-md sm:max-w-md md:max-w-lg lg:max-w-2xl bg-white/20 border border-purple-300 backdrop-blur-sm p-6 sm:p-8 rounded-2xl shadow-2xl mx-4 transition-all duration-300
  "
>
    {/* Heading */}
    <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold mb-2 text-center text-gray-800">
      Welcome Back
    </h2>

    <p className="text-sm sm:text-base text-gray-600 mb-8 text-center">
      Don’t have an account?{" "}
      <a
        href="/signup"
        className="text-[#6f00ff] font-semibold hover:underline hover:text-[#e6007e]"
      >
        Sign Up
      </a>
    </p>

    {/* Form */}
    <form onSubmit={handleEmailLogin} className="space-y-5">
      <div>
        <label className="block text-gray-700 font-bold mb-1">
          E-mail
        </label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Enter your email"
          required
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6f00ff]/70 text-gray-700 placeholder-gray-400"
        />
      </div>

      <div>
        <label className="block text-gray-700 font-bold mb-0.5">
          Password
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter your password"
          required
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#e6007e]/70 text-gray-700 placeholder-gray-400"
        />
      </div>

      <div className="text-right">
        <a
          href="/forgot-password"
          className="text-sm text-[#6f00ff] hover:underline"
        >
          Forgot Password?
        </a>
      </div>

      {error && (
        <div className="text-red-600 font-medium bg-red-100/50 px-3 py-2 rounded-md text-center">
          {error}
        </div>
      )}

      <button
        type="submit"
        className="
          w-full mt-2 bg-gradient-to-r from-purple-700 via-blue-800 to-blue-900  text-white px-6 py-2.5 
          rounded-lg font-semibold shadow-lg hover:opacity-90 hover:shadow-xl transition duration-300" >
        Sign In
      </button>
    </form>

    {/* Divider */}
    <div className="my-4 flex items-center">
      <div className="flex-1 h-px bg-gray-300" />
      <span className="px-3 text-gray-500 text-sm">or</span>
      <div className="flex-1 h-px bg-gray-300" />
    </div>

    {/* Google Sign-in */}
    <button
      onClick={handleGoogleSignIn}
      className="
        flex items-center justify-center w-full 
        bg-white border border-gray-300 
        text-gray-700 font-semibold py-2.5 
        rounded-lg shadow-sm hover:shadow-md 
        transition
      "
    >
      <Image
        src='https://www.svgrepo.com/show/475656/google-color.svg'
        width={22}
        height={22}
        alt='Google'
        className='mr-3'
      />
      Sign in with Google
    </button>
  </motion.div>
);

}
