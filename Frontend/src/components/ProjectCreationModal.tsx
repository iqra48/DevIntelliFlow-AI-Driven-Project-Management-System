"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { createProject } from "@/lib/project";
import toast from "react-hot-toast";
interface ProjectCreationModalProps {
  onClose: () => void;
}

export default function ProjectCreationModal({
  onClose,
}: ProjectCreationModalProps) {
  const router = useRouter();
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);

  const [projectTitle, setProjectTitle] = useState("");
  const [projectDetails, setProjectDetails] = useState("");
  const [projectPriority, setProjectPriority] = useState<
    "Low" | "Medium" | "High" |"Urgent"
  >("Medium");
  const [projectStatus, setProjectStatus] = useState<
    "Not Started" | "In Progress" | "Completed" | "On Hold"
  >("Not Started");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const saveProject = async () => {

    if (!user) {
      alert("⚠️ You must be logged in to create a project.");
      return;
    }

    setIsSaving(true);

    try {
      const projectId = await createProject(user.uid, user.email || "", {
        name: projectTitle,
        description: projectDetails,
        priority: projectPriority,
        status: projectStatus,
      });

      onClose();

      router.push(
        `/projects/${projectId}?name=${encodeURIComponent(projectTitle)}`
      );
    } catch (error) {
      console.error("❌ Failed to create project:", error);
      toast.error("Oops! Something went wrong while creating your project.");
    } finally {
      setIsSaving(false);
    }
  };

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose}></div>

      {/* Modal */}
      <div className="relative bg-white p-6 sm:p-8 rounded-xl shadow-lg w-full max-w-lg mx-4 z-10">
        <h2 className="font-bold text-2xl mb-1">Create a New Project</h2>
        <p className="text-gray-400 mb-4 text-sm">Enter the project details below to get things rolling.</p>
        <hr className="mb-5 text-gray-400" />

        {/* Form */}
        <form
          onSubmit={(e) => {
             e.preventDefault(); // prevent page reload

            if (projectTitle.trim().length < 3) {
              toast.error(" Project name must be at least 3 characters");
              return;
            }
                    
            saveProject();
          }}
        >
          {/* Project Name */}
          <label className="block font-semibold mb-1 text-gray-600">Project Name</label>
          <input
            type="text"
            placeholder="Enter Project name..."
            required
            value={projectTitle}
            onChange={(e) => setProjectTitle(e.target.value)}
            className="w-full border border-gray-300 rounded-lg p-2 mb-2 text-sm text-gray-600 font-light"
          />

          {/* Project Description */}
          <label className="block font-semibold mb-1 text-gray-600">Project Description</label>
          <textarea
            placeholder="Write a short description..."
            value={projectDetails}
            onChange={(e) => setProjectDetails(e.target.value)}
            className="w-full border border-gray-300 rounded-lg p-2 mb-2 text-sm text-gray-600 font-light"
          />

          {/* Priority */}
          <label className="block font-semibold mb-1 text-gray-600">Priority</label>
          <div className="flex gap-2 mb-4">
            {(["Low", "Medium", "High", "Urgent"] as const).map((level) => {
              const baseColors =
                level === "Low"
                  ? "bg-stone-200 text-gray-600 border border-stone-300"
                  : level === "Medium"
                  ? "bg-yellow-100 text-gray-600 border border-yellow-200"
                  : level === "High"
                  ? "bg-orange-100 text-gray-600 border border-orange-200"
                  : "bg-red-100 text-gray-600 border border-red-200";

              const activeColors =
                level === "Low"
                  ? "bg-stone-400 text-white border-stone-200"
                  : level === "Medium"
                  ? "bg-yellow-500 text-white border-blue-400"
                  : level === "High"
                  ? "bg-orange-500 text-white border-orange-400"
                  : "bg-red-500 text-white border-red-400";

              return (
                <button
                  key={level}
                  type="button"
                  onClick={() => setProjectPriority(level)}
                  className={`px-4 py-2 text-sm rounded-lg transition-colors ${
                    projectPriority === level ? activeColors : baseColors
                  }`}
                >
                  {level}
                </button>
              );
            })}
          </div>

          {/* Status */}
          <label className="block font-semibold mb-1 text-gray-600">Status</label>
          <div className="flex flex-wrap gap-2 mb-4">
            {(["Not Started", "In Progress", "Completed", "On Hold"] as const).map((status) => {
              const baseColors =
                status === "Not Started"
                  ? "bg-pink-200 text-gray-600 border border-pink-200"
                  : status === "In Progress"
                  ? "bg-blue-100 text-gray-600 border border-blue-200"
                  : status === "Completed"
                  ? "bg-green-200 text-gray-600 border border-green-300"
                  : "bg-purple-200 text-gray-600 border border-purple-300";

              const activeColors =
                status === "Not Started"
                  ? "bg-pink-500 text-white border-gray-400"
                  : status === "In Progress"
                  ? "bg-blue-500 text-white border-blue-400"
                  : status === "Completed"
                  ? "bg-green-500 text-white border-green-400"
                  : "bg-purple-500 text-white border-purple-400";

              return (
                <button
                  key={status}
                  type="button"
                  onClick={() => setProjectStatus(status)}
                  className={`px-4 py-2 text-sm rounded-lg transition-colors ${
                    projectStatus === status ? activeColors : baseColors
                  }`}
                >
                  {status}
                </button>
              );
            })}
          </div>

          {/* Buttons */}
          <div className="flex justify-end gap-2 mt-10">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="px-4 py-1.5 bg-purple-700 text-white rounded-lg hover:bg-purple-800 disabled:opacity-60"
            >
              {isSaving ? "Creating..." : "Create Project"}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
