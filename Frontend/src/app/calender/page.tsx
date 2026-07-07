"use client";

import { useEffect, useState } from "react";
import { collection, onSnapshot, query, where } from "firebase/firestore";
import { db } from "@/firebase/firebaseConfig";
import { useAuth } from "@/context/AuthContext";
import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";
import { Project } from "@/types/project";
import DeadlineCalendar from "@/components/DeadlineCalendar/DeadlineCalendar";

export default function CalendarPage() {
  const { user, loading: checkingAuth } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loadingData, setLoadingData] = useState(true);

  useEffect(() => {
    if (!user) {
      setProjects([]);
      setLoadingData(false);
      return;
    }

    setLoadingData(true);

    const q = query(collection(db, "projects"), where("ownerId", "==", user.uid));

    const unsub = onSnapshot(
      q,
      (snap) => {
        const data: Project[] = snap.docs.map((doc) => ({
          id: doc.id,
          ...doc.data(),
        })) as Project[];

        setProjects(data);
        setLoadingData(false);
      },
      (error) => {
        console.error("CalendarPage snapshot error:", error);
        setProjects([]);
        setLoadingData(false);
      }
    );

    // Cleanup listener on unmount or user change
    return () => unsub();
  }, [user]);

  if (checkingAuth) {
    return (
      <section className="flex h-screen items-center justify-center">
        <span className="text-gray-600 text-lg animate-pulse">
          Checking your account...
        </span>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="flex h-screen items-center justify-center">
        <div className="rounded-xl bg-[#F8F9FB]/90 p-6 shadow-md text-center max-w-sm">
          <h2 className="text-gray-700 font-medium">
            You need to sign in to access your workspace.
          </h2>
        </div>
      </section>
    );
  }
  return (
    <div className="flex flex-col h-screen">
      <Navbar />
      <div className="flex flex-1">
        <Sidebar />

        {/* Calendar takes full width, no extra white box */}
        <main
          className="bg-gray-50 flex-1 flex flex-col gap-6 px-3 sm:px-6 md:px-8 pt-22 pb-8 ml-12 lg:ml-64"
        >
          {loadingData ? (
            <p className="text-gray-500">Loading calendar...</p>
          ) : (
            <DeadlineCalendar projects={projects} />
          )}
        </main>
      </div>
    </div>
  );
}
