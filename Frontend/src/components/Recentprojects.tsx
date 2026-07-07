"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { db } from "@/firebase/firebaseConfig";
import Link from "next/link";
import {
  collection,
  query,
  where,
  orderBy,
  limit,
  onSnapshot,
  Timestamp,
} from "firebase/firestore";
import type { Project } from "@/types/project";
import { Calendar, Clock } from "lucide-react";

const formatDate = (value: Timestamp | string | null | undefined) => {
  if (!value) return "-";

  if (typeof value === "string") {
    return new Date(value).toLocaleDateString();
  }

  if (value instanceof Timestamp) {
    return new Date(value.seconds * 1000).toLocaleDateString();
  }

  return "-";
};

export default function RecentProjects() {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);

  useEffect(() => {
    // Agar user nahi hai, listener attach mat karo
    if (!user) {
      setProjects([]); // clear projects on logout
      return;
    }

    const q = query(
      collection(db, "projects"),
      where("ownerId", "==", user.uid),
      orderBy("lastOpenedAt", "desc"),
      limit(3)
    );

    // Listener attach
    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const fetched: Project[] = snapshot.docs.map((doc) => {
          const data = doc.data();
          return {
            id: doc.id,
            name: data.name ?? "Unnamed Project",
            description: data.description ?? "",
            priority: data.priority ?? "Medium",
            createdAt: data.createdAt as Timestamp | null,
            lastOpenedAt: data.lastOpenedAt as Timestamp | null,
            status: data.status,
            startDate: data.startDate,
            timeEstimate: data.timeEstimate,
            dueDate: data.dueDate ?? null,
            ownerId: data.ownerId ?? user.uid,
            ownerEmail: data.ownerEmail ?? user.email,
          };
        });
        setProjects(fetched);
      },
      (error) => {
        console.error("Snapshot error:", error);
        if (error.code === "permission-denied") {
          setProjects([]);
        }
      }
    );

    // Cleanup listener on unmount or user change
    return () => unsubscribe();
  }, [user]);
  return (
    <section className="w-full h-auto flex flex-col ">
      {/* Heading */}
      <div className="mb-4">
        <h2 className="text-2xl sm:text-2xl md:text-2xl font-bold mb-1">
          Recent Projects
        </h2>
        <p className="text-sm text-gray-500">
          A quick glance at your most recently opened projects
        </p>
      </div>

      {projects.length === 0 ? (
        <p className="text-gray-500 text-center mt-5 text-lg">
          No recent projects found.
        </p>
      ) : (
        <>
          {/* Desktop Table */}
          <div className="hidden md:flex flex-col flex-1 rounded-md bg-white   shadow overflow-hidden">
            <div className="overflow-x-auto w-full">
              <table className="table w-full table-fixed text-center text-sm border-collapse">
                <thead className="bg-stone-200 text-gray-800 text-sm uppercase tracking-wide font-semibold">
                  <tr>
                    <th className="py-4 px-4">Project Name</th>
                    <th className="py-4 px-4">Priority</th>
                    <th className="py-4 px-4">Status</th>
                    <th className="py-4 px-4">Created At</th>
                    <th className="py-4 px-4">Due Date</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((project, idx) => (
                    <tr
                      key={project.id}
                      className={`transition border-b ${
                        idx % 2 === 0 ? "bg-white" : "bg-stone-50"
                      } hover:bg-stone-100`}
                    >
                      <td className="py-4 px-4 font-medium text-stone-800 truncate max-w-[160px]">
                        <Link
                          href={`/projects/${project.id}`}
                          className="hover:text-blue-600 hover:underline"
                        >
                          {project.name}
                        </Link>
                      </td>
                      <td className="py-4 px-4">
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-medium shadow-sm ${
                            project.priority === "Urgent"
                              ? "bg-red-500 text-white"
                              : project.priority === "High"
                              ? "bg-orange-500 text-white"
                              : project.priority === "Medium"
                              ? "bg-yellow-500 text-white"
                              : project.priority === "Low"
                              ? "bg-stone-400 text-white"
                              : "bg-purple-500 text-white"
                          }`}
                        >
                          {project.priority}
                        </span>
                      </td>
                      <td className="py-4 px-4">
                        <span
                          className={`px-2.5 py-1 rounded-full text-[11px] font-medium ring-1 shadow-sm whitespace-nowrap ${
                            project.status === "Completed"
                              ? "bg-green-500 text-white ring-green-200"
                              : project.status === "In Progress"
                              ? "bg-blue-500 text-white ring-blue-200"
                              : project.status === "Not Started"
                              ? "bg-pink-500 text-white ring-gray-300"
                              : project.status === "On Hold"
                              ? "bg-purple-500 text-white ring-purple-200"
                              : "bg-gray-100 text-white ring-gray-200"
                          }`}
                        >
                          {project.status}
                        </span>
                      </td>
                      <td className="py-4 px-4 text-gray-600 whitespace-nowrap">
                        {formatDate(project.createdAt)}
                      </td>
                      <td className="py-4 px-4 text-red-600 whitespace-nowrap">
                        {formatDate(project.dueDate)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td
                      colSpan={5}
                      className="py-3 px-4 border-t text-right bg-stone-100"
                    >
                      <Link
                        href="/projects"
                        className="text-lg font-medium text-purple-600 hover:text-purple-700 hover:underline"
                      >
                        See all projects
                      </Link>
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden space-y-2">
            {projects.map((project) => (
              <div
                key={project.id}
                className="p-3 bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition flex flex-col gap-1.5"
              >
                {/* Project Name */}
                <Link
                  href={`/projects/${project.id}`}
                  className="text-base font-semibold text-gray-900 hover:text-purple-700 hover:underline truncate"
                >
                  {project.name}
                </Link>

                {/* Priority + Status badges */}
                <div className="flex gap-2 flex-wrap">
                  <span
                    className={`px-2.5 py-1 rounded-full text-[11px] font-medium ring-1 shadow-sm whitespace-nowrap ${
                       project.priority === "Urgent"
                              ? "bg-red-500 text-white"
                              : project.priority === "High"
                              ? "bg-orange-500 text-white"
                              : project.priority === "Medium"
                              ? "bg-yellow-500 text-white"
                              : project.priority === "Low"
                              ? "bg-stone-400 text-white"
                              : "bg-purple-500 text-white"
                    }`}
                  >
                    {project.priority}
                  </span>

                   <span
                          className={`px-2.5 py-1 rounded-full text-[11px] font-medium ring-1 shadow-sm whitespace-nowrap ${
                            project.status === "Completed"
                              ? "bg-green-500 text-white ring-green-200"
                              : project.status === "In Progress"
                              ? "bg-blue-500 text-white ring-blue-200"
                              : project.status === "Not Started"
                              ? "bg-pink-500 text-white ring-pink-300"
                              : project.status === "On Hold"
                              ? "bg-purple-500 text-white ring-purple-200"
                              : "bg-gray-100 text-white ring-gray-200"
                          }`}
                        >
                          {project.status}
                        </span>
                </div>

                {/* Dates with Lucide Icons */}
                <div className="text-[11px] text-gray-400 space-y-0.5">
                  <div className="flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-gray-400" />
                    <span>Created: {formatDate(project.createdAt)}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3 text-pink-700" />
                    <span className="text-pink-700">
                      Due: {formatDate(project.dueDate)}
                    </span>
                  </div>
                </div>
              </div>
            ))}

            {/* Mobile Footer Link */}
            <div className="pt-2 text-right">
              <Link
                href="/projects"
                className="text-sm font-semibold text-purple-600 hover:text-purple-700 hover:underline"
              >
                See all projects →
              </Link>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
