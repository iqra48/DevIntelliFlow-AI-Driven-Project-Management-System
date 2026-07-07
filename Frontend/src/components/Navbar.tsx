"use client";

import Image from "next/image";
import { Playfair_Display } from "next/font/google";
import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { auth, db } from "@/firebase/firebaseConfig";
import { onAuthStateChanged, User } from "firebase/auth";
import { collection, doc, onSnapshot, query, where } from "firebase/firestore";
import Avatar from "@/components/Avatar";
import { HelpCircle, Search } from "lucide-react";
import NavbarSearch from "@/components/Navbarsearch";
import { Project } from "@/types/project";

const playfair = Playfair_Display({
  weight: "700",
  subsets: ["latin"],
});

export default function Navbar() {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<any>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let unsubscribeAuth: (() => void) | null = null;
    let unsubscribeProfile: (() => void) | null = null;
    let unsubscribeProjects: (() => void) | null = null;

    unsubscribeAuth = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);

      if (currentUser) {
        // Profile listener
        const docRef = doc(db, "users", currentUser.uid);
        unsubscribeProfile = onSnapshot(docRef, (docSnap) => {
          if (docSnap.exists()) {
            setProfile(docSnap.data());
          } else {
            setProfile({
              firstName: currentUser.displayName?.split(" ")[0] || "",
              lastName: currentUser.displayName?.split(" ")[1] || "",
              email: currentUser.email,
            });
          }
        });

        // Projects listener
        const q = query(collection(db, "projects"), where("ownerId", "==", currentUser.uid));
        unsubscribeProjects = onSnapshot(q, (snap) => {
          const projList: Project[] = snap.docs.map((doc) => ({
            id: doc.id,
            ...doc.data(),
          })) as Project[];
          setProjects(projList);
        });
      } else {
        // User signed out
        setProjects([]);
        setProfile(null);
      }
    });

    return () => {
      // Cleanup all listeners
      if (unsubscribeAuth) unsubscribeAuth();
      if (unsubscribeProfile) unsubscribeProfile();
      if (unsubscribeProjects) unsubscribeProjects();
    };
  }, []);

  // Close search on ESC
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowSearch(false);
    };
    document.addEventListener("keydown", handleEsc);
    return () => document.removeEventListener("keydown", handleEsc);
  }, []);

  // Close search on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSearch(false);
      }
    };
    if (showSearch) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showSearch]);
  return (
    <header className="fixed top-0 left-0 w-full h-14 bg-gradient-to-r from-purple-800 via-purple-800 to-blue-900 text-white shadow-xl z-50">
      <div className="w-full h-full px-3 sm:px-4 flex items-center justify-between">
        {/* Left Section: Logo + Brand/Search */}
        <div className="flex items-center gap-2 flex-1 min-w-0" ref={searchRef}>
          <Image
            src="/logo_trans.png"
            alt="DevIntelliFlow Logo"
            width={36}
            height={36}
            className="h-9 w-auto object-contain"
          />

          {/* Brand text (hidden when search active on sm) */}
          <span
            className={`${playfair.className} ${
              showSearch ? "hidden sm:block" : "block"
            } text-white text-lg sm:text-xl font-bold tracking-wide transition-all duration-300`}
          >
            DevIntelliFlow
          </span>

          {/* Search bar (sm only + active) */}
          <div
            className={`sm:hidden flex-1 transition-all duration-300 ${
              showSearch
                ? "opacity-100 translate-x-0"
                : "opacity-0 -translate-x-2 pointer-events-none"
            }`}
          >
            <NavbarSearch
              projects={projects}
              onSearch={(items) => console.log("Navbar searched:", items)}
            />
          </div>
        </div>

        {/* Right Section: Search toggle + Help + Avatar */}
        <div className="flex items-center gap-3 sm:gap-6">
          {/* Search toggle (sm only, hidden when active) */}
          {!showSearch && (
            <button
              className="sm:hidden p-2 rounded-md hover:bg-white/10 transition-colors"
              onClick={() => setShowSearch(true)}
            >
              <Search className="w-5 h-5 text-white" />
            </button>
          )}

          {/* Navbar Search (desktop only) */}
          <div className="hidden sm:block">
            <NavbarSearch
              projects={projects}
              onSearch={(items) => console.log("Navbar searched:", items)}
            />
          </div>

          {/* Help Icon */}
          <Link href="/help" aria-label="Help">
            <HelpCircle className="text-white hover:text-indigo-200 w-5 h-5 transition-colors duration-300" />
          </Link>

          {/* Avatar */}
          <Link href="/userprofile" aria-label="Profile">
            {profile ? (
              <div className="relative">
                <Avatar
                  name={`${profile.firstName || ""} ${profile.lastName || ""}`}
                  email={profile.email}
                  size="w-9 h-9"
                />
                <span className="absolute inset-0 rounded-full ring-4 ring-gray-400 pointer-events-none" />
              </div>
            ) : (
              <div className="w-9 h-9 rounded-full bg-gray-300 ring-2 ring-gray-500" />
            )}
          </Link>
        </div>
      </div>
    </header>
  );
}
