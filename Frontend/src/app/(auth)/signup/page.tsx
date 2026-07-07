"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithGoogle } from "@/firebase/Signin";
import {
  createUserWithEmailAndPassword,
  sendEmailVerification,
} from "firebase/auth";
import { auth, db } from "@/firebase/firebaseConfig";
import { FirebaseError } from "firebase/app";
import { doc, setDoc, serverTimestamp, getDoc } from "firebase/firestore";
import Image from "next/image";

export default function SignupPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  //  Helper to create Firestore user doc if it doesn't exist
  const createUserDoc = async (
    uid: string,
    userEmail: string,
    displayName?: string,
    photoURL?: string
  ) => {
    const userRef = doc(db, "users", uid);
    const existingDoc = await getDoc(userRef);

    if (!existingDoc.exists()) {
      await setDoc(userRef, {
        name: displayName || name,
        email: userEmail,
        photoURL: photoURL || "",
        bio: "",
        role: "viewer",
        createdAt: serverTimestamp(),
      });
    }
  };

  //  Google Signup
  const handleGoogleSignup = async () => {
    try {
      const user = await signInWithGoogle();
      if (!user) return;

      await createUserDoc(
        user.uid,
        user.email!,
        user.displayName || "",
        user.photoURL || ""
      );

      console.log("Signed up with Google:", user.displayName);
      router.push("/dashboard");
    } catch (err) {
      console.error(err);
      setError("Google sign-up failed.");
    }
  };

  //  Email/Password Signup
  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      const userCredential = await createUserWithEmailAndPassword(
        auth,
        email,
        password
      );
      const user = userCredential.user;

      // Save profile in Firestore
      await createUserDoc(user.uid, email, name);

      // Send email verification
      await sendEmailVerification(user);
      setSuccess("Verification email sent. Please check your inbox.");

      localStorage.setItem("awaitingVerification", "true");
      router.push("/emailverify");
    } catch (_err: unknown) {
      console.error(_err);
      if (_err instanceof FirebaseError) {
        if (_err.code === "auth/email-already-in-use") {
          setError("This email is already in use.");
        } else {
          setError(_err.message);
        }
      } else {
        setError("An unexpected error occurred.");
      }
    }
  };

  return (
    
  <div className="w-full max-w-md sm:max-w-md md:max-w-lg lg:max-w-2xl bg-white/20 border border-purple-300 backdrop-blur-sm p-6 sm:p-8 rounded-2xl shadow-2xl mx-4 transition-all duration-300">
    <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold mb-2 text-center text-gray-800">
      Create Account
    </h2>
    <h4 className="text-sm sm:text-base text-gray-500 mb-6 text-center">
      Already have an account?{" "}
      <a
        href="/login"
        className="text-purple-700 font-bold hover:underline"
      >
        Sign in
      </a>
    </h4>

    <form onSubmit={handleSignup} className="space-y-4 text-left">
      <div>
        <label className="block text-gray-700 font-bold">Name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter your name"
          required
          className="w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400 text-gray-500"
        />
      </div>

      <div>
        <label className="block text-gray-700 font-bold">E-mail</label>
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
        <label className="block text-gray-700 font-bold">Password</label>
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
        <label className="block text-gray-700 font-bold">Confirm Password</label>
        <input
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="Confirm your password"
          required
          className="w-full px-4 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400 text-gray-500"
        />
      </div>

      {/* Messages */}
      {error && <div className="text-red-600 font-medium">{error}</div>}
      {success && <div className="text-green-600 font-medium">{success}</div>}

      <button
        type="submit"
        className="w-full mt-4 bg-gradient-to-r from-purple-700 via-blue-800 to-blue-900 text-white px-6 py-2 rounded-md font-semibold hover:opacity-90 transition"
      >
        Sign Up
      </button>
    </form>

    <div className="mt-6">
      <button
        onClick={handleGoogleSignup}
        className="flex items-center justify-center w-full bg-white border text-gray-700 font-semibold py-2 rounded-md shadow hover:shadow-md transition"
      >
        <Image
          src="https://www.svgrepo.com/show/475656/google-color.svg"
          alt="Google"
          width={24}
          height={24}
          className="mr-2"
        />
        Sign up with Google
      </button>
    </div>
  </div>
);

}
