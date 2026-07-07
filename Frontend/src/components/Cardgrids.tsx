"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { db } from "@/firebase/firebaseConfig";
import { collection, query, where, onSnapshot } from "firebase/firestore";
import type { Project } from "@/types/project";
import { ListTodo, CircleCheckBig, ClockAlert, Gauge } from "lucide-react";
import Image from "next/image";

export default function CardGrid() {
  const { user } = useAuth();
  const [activeProjects, setActiveProjects] = useState(0);
  const [completedProjects, setCompletedProjects] = useState(0);
  const [overdueProjects, setOverdueProjects] = useState(0);
  const [highPriorityProjects, setHighPriorityProjects] = useState(0);

  useEffect(() => {
    if (!user) {
      setActiveProjects(0);
      setCompletedProjects(0);
      setOverdueProjects(0);
      setHighPriorityProjects(0);
      return;
    }

    const now = new Date();
    const startOfMonth = `${now.getFullYear()}-${String(
      now.getMonth() + 1
    ).padStart(2, "0")}-01`;
    const endOfMonthDate = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const endOfMonth = `${endOfMonthDate.getFullYear()}-${String(
      endOfMonthDate.getMonth() + 1
    ).padStart(2, "0")}-${String(endOfMonthDate.getDate()).padStart(2, "0")}`;

    const q = query(
      collection(db, "projects"),
      where("ownerId", "==", user.uid),
      where("dueDate", ">=", startOfMonth),
      where("dueDate", "<=", endOfMonth)
    );

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        let active = 0;
        let completed = 0;
        let overdue = 0;
        let highPriority = 0;

        const today = new Date();

        snapshot.forEach((doc) => {
          const data = doc.data() as Project;

          if (data.status === "In Progress") active++;
          if (data.status === "Completed") completed++;
          if (data.dueDate) {
            const projectDue = new Date(data.dueDate);
            if (projectDue < today && data.status !== "Completed") overdue++;
          }
          if (data.priority === "High" || data.priority === "Urgent") highPriority++;
        });

        setActiveProjects(active);
        setCompletedProjects(completed);
        setOverdueProjects(overdue);
        setHighPriorityProjects(highPriority);
      },
      (error) => {
        console.error("Snapshot error:", error);
        if (error.code === "permission-denied") {
          setActiveProjects(0);
          setCompletedProjects(0);
          setOverdueProjects(0);
          setHighPriorityProjects(0);
        }
      }
    );

    return () => unsubscribe();
  }, [user]);

  return (
    <div className="grid grid-cols-2 gap-4 w-full h-full auto-rows-min lg:auto-rows-fr">
      {/* Active Projects */}
      <div className="relative shadow-md p-4 flex flex-col h-full justify-between bg-gradient-to-r from-blue-100 to-blue-200 overflow-hidden rounded-md">
        <Image
          src="/blue_bar_chart.png"
          alt=""
          fill
          className="object-cover opacity-10 pointer-events-none"
        />
        <div className="w-10 h-10 sm:w-11 sm:h-11 md:w-12 md:h-12 rounded-full bg-gradient-to-r from-blue-500 to-blue-700 flex items-center justify-center shadow-inner mb-2 relative z-10">
          <ListTodo className="w-6 h-6 sm:w-7 sm:h-7 md:w-8 md:h-8 text-white fill-white" />
        </div>
        <p className="text-[clamp(1.5rem,2.5vw,3rem)] font-bold text-gray-700 leading-tight relative z-10">
          {activeProjects}
        </p>
        <h3 className="text-blue-900 tracking-wide leading-snug text-[clamp(0.85rem,1.5vw,1.1rem)] font-semibold md:font-bold mt-1 relative z-10">
          Active Projects
        </h3>
        <p className="text-[clamp(0.65rem,0.9vw,0.85rem)] font-normal text-opacity-90 text-blue-800 mt-1 relative z-10 leading-snug min-h-[18px]">
          Currently in progress this month
        </p>
      </div>

      {/* Completed Projects */}
      <div className="relative shadow-md p-4 flex flex-col h-full justify-between bg-gradient-to-r from-green-100 to-green-50 overflow-hidden rounded-md">
        <Image
          src="/comp_bg.svg"
          alt=""
          fill
          className="object-cover opacity-20 pointer-events-none"
        />
        <div className="w-10 h-10 sm:w-11 sm:h-11 md:w-12 md:h-12 rounded-full bg-gradient-to-r from-green-500 to-green-700 flex items-center justify-center shadow-inner mb-2 relative z-10">
          <CircleCheckBig className="w-6 h-6 sm:w-7 sm:h-7 md:w-8 md:h-8 text-white" />
        </div>
        <p className="text-[clamp(1.5rem,2.5vw,3rem)] font-bold text-gray-700 leading-tight relative z-10">
          {completedProjects}
        </p>
        <h3 className="text-green-900 tracking-wide leading-snug text-[clamp(0.85rem,1.5vw,1.1rem)] font-semibold md:font-bold mt-1 relative z-10">
          Completed Projects
        </h3>
        <p className="text-[clamp(0.65rem,0.9vw,0.85rem)] font-normal text-opacity-90 text-green-900 mt-1 relative z-10 leading-snug min-h-[18px]">
          Completed so far this month
        </p>
      </div>

      {/* Overdue Projects */}
      <div className="relative shadow-md p-4 flex flex-col justify-between h-full bg-gradient-to-r from-red-200 to-red-300 overflow-hidden rounded-md">
        <Image
          src="/redchart.png"
          alt=""
          fill
          className="object-cover opacity-15 pointer-events-none"
        />
        <div className="w-10 h-10 sm:w-11 sm:h-11 md:w-12 md:h-12 rounded-full bg-gradient-to-r from-red-500 to-red-700 flex items-center justify-center shadow-inner mb-2 relative z-10">
          <ClockAlert className="w-6 h-6 sm:w-7 sm:h-7 md:w-8 md:h-8 text-white" />
        </div>
        <p className="text-[clamp(1.5rem,2.5vw,3rem)] font-bold text-gray-700 leading-tight relative z-10">
          {overdueProjects}
        </p>
        <h3 className="text-red-900 tracking-wide leading-snug text-[clamp(0.85rem,1.5vw,1.1rem)] font-semibold md:font-bold mt-1 relative z-10">
          Overdue Projects
        </h3>
        <p className="text-[clamp(0.65rem,0.9vw,0.85rem)] font-normal text-opacity-90 text-red-700 mt-1 relative z-10 leading-snug min-h-[18px]">
          Delayed from previous months
        </p>
      </div>

      {/* High Priority */}
      <div className="relative shadow-md p-4 flex flex-col justify-between h-full bg-gradient-to-r from-pink-200 to-violet-300 overflow-hidden rounded-md">
        <Image
          src="/pur_bg.svg"
          alt=""
          fill
          className="object-cover opacity-20 pointer-events-none"
        />
        <div className="w-10 h-10 sm:w-11 sm:h-11 md:w-12 md:h-12 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 flex items-center justify-center shadow-inner mb-2 relative z-10">
          <Gauge className="w-6 h-6 sm:w-7 sm:h-7 md:w-8 md:h-8 text-white" />
        </div>
        <p className="text-[clamp(1.5rem,2.5vw,3rem)] font-bold text-gray-700 leading-tight relative z-10">
          {highPriorityProjects}
        </p>
        <h3 className="text-purple-900 tracking-wide leading-snug text-[clamp(0.85rem,1.5vw,1.1rem)] font-semibold md:font-bold mt-1 relative z-10">
          High Priority
        </h3>
        <p className="text-[clamp(0.65rem,0.9vw,0.85rem)] font-normal text-opacity-90 text-purple-900 mt-0.5 relative z-10 leading-snug min-h-[18px]">
          Critical for month-end goals
        </p>
      </div>
    </div>
  );
}
