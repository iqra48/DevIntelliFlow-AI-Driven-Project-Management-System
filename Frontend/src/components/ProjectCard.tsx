"use client";

import { Project } from "@/types/project";
import { Calendar } from "lucide-react";
import { format } from "date-fns";

// Status colors
const statusStyles: Record<Project["status"], string> = {
  Completed: "bg-emerald-500 text-white",
  "In Progress": "bg-blue-500 text-white",
  "Not Started": "bg-pink-500 text-white",
  "On Hold": "bg-purple-500 text-white",
};

interface ProjectCardProps {
  project: Project;
}

function toMillis(d: any): number | null {
  if (!d && d !== 0) return null;
  // Firestore Timestamp has toDate()
  if (d instanceof Date) return d.getTime();
  if (typeof d?.toDate === "function") {
    try {
      return d.toDate().getTime();
    } catch {
      return null;
    }
  }
  const parsed = new Date(d);
  return isNaN(parsed.getTime()) ? null : parsed.getTime();
}

function computeProgressPercent(project: Project): number {
  if (project.status === "Completed") return 100;

  const start = toMillis(project.startDate);
  const due = toMillis(project.dueDate);
  const now = Date.now();

  if (start == null || due == null) {
    // missing dates will lead to show 0
    return 0;
  }

  const duration = due - start;

  if (duration <= 0) {

    return now >= due ? 100 : 0;
  }

  const raw = ((now - start) / duration) * 100;
  const clamped = Math.round(Math.max(0, Math.min(100, raw)));
  return clamped;
}

export default function ProjectCard({ project }: ProjectCardProps) {
  const progressPercent = computeProgressPercent(project);

  // Color for progress indicator based on status
  const progressColorClass =
    project.status === "Completed"
      ? "bg-emerald-500"
      : project.status === "In Progress"
      ? "bg-blue-500"
      : project.status === "On Hold"
      ? "bg-purple-500"
      : "bg-pink-500";

  return (
   <div className="relative flex bg-white border border-gray-300 rounded-md shadow-sm hover:shadow-md transition overflow-hidden">
  <div
    style={{ width: project.priority === "Urgent" ? "3.5px" : "4px" }}
    className={`flex-shrink-0 ${
      project.priority === "Urgent"
        ? "bg-red-600"
        : project.priority === "High"
        ? "bg-orange-500"
        : project.priority === "Medium"
        ? "bg-yellow-500"
        : project.priority === "Low"
        ? "bg-stone-400"
        : "bg-gray-50"
    }`}
    aria-hidden="true"
  />

      <div className="flex-1 p-4 space-y-3">
        {/* Status Badge */}
        <div className="flex">
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-semibold ${statusStyles[project.status]}`}
          >
            {project.status}
          </span>
        </div>

        {/* Project title + description */}
        <div>
          <h2 className="text-lg font-bold">{project.name}</h2>
          <p className="text-sm text-gray-500 line-clamp-2">{project.description}</p>
        </div>

        {/* Progress bar */}
        <div>
          <div className="flex justify-between text-xs text-gray-500">
            <span>Progress</span>
            <span>{progressPercent}%</span>
          </div>
          <div
            className="w-full bg-gray-200 rounded-full h-1.5 mt-1"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progressPercent}
          >
            <div
              className={`${progressColorClass} h-2 rounded-full transition-all`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Created date */}
        {project.createdAt && (
          <div className="flex items-center gap-1 text-xs text-gray-400">
            <Calendar className="w-4 h-4" />
            <span>
              {format(
                project.createdAt instanceof Date ? project.createdAt : project.createdAt?.toDate(),
                "MMM dd, yyyy"
              )}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
