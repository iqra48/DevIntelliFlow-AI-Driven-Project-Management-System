"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { db } from "@/firebase/firebaseConfig";
import { doc, getDoc, updateDoc } from "firebase/firestore";
import { Project } from "@/types/project";
import toast from "react-hot-toast";
import {
  Calendar,
  Flag,
  Clock,
  CheckCircle,
  SquarePen,
  AlertCircle,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function ProjectOverviewPage() {
  const { id } = useParams();
  const { user } = useAuth();

  const [editable, setEditable] = useState<Project | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isReadOnly, setIsReadOnly] = useState(false);

  useEffect(() => {
    const fetchProject = async () => {
      if (!id) return;
      const snap = await getDoc(doc(db, "projects", id as string));
      if (!snap.exists()) return;

      const data = { id: snap.id, ...snap.data() } as Project;
      setEditable(data);

      const ownerId = data.ownerId;
      if (!user && data.shareLinkEnabled) setIsReadOnly(true);
      else if (user && user.uid !== ownerId) setIsReadOnly(true);
    };
    fetchProject();
  }, [id, user]);

  const handleChange = (
    field: keyof Project,
    value: string | number | Date | null
  ) => {
    if (isReadOnly) return;

    setEditable((prev) => {
      if (!prev) return prev;
      const updated: Project = { ...prev, [field]: value };

      setError(null);

      if (field === "startDate" || field === "dueDate") {
        const start = updated.startDate ? new Date(updated.startDate) : null;
        const due = updated.dueDate ? new Date(updated.dueDate) : null;

        if (start && due) {
          if (due < start) setError("Due date cannot be earlier than start date.");
          else {
            const diff = Math.ceil((due.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
            updated.timeEstimate = diff > 0 ? diff : 0;
          }
        } else updated.timeEstimate = undefined;
      }

      return updated;
    });
  };

  const handleSave = async () => {
    if (!editable || !id || isReadOnly) return;
    if (error) {
      toast.error("Please fix the date errors before saving.");
      return;
    }

    setSaving(true);
    try {
      const { id, ...dataToSave } = editable;
      await updateDoc(doc(db, "projects", id as string), dataToSave);
      toast.success("Project updated successfully");
    } catch (err) {
      console.error(err);
      toast.error("Failed to update project");
    } finally {
      setSaving(false);
    }
  };

  if (!editable) return <p>Loading project...</p>;

  const statusColors: Record<string, string> = {
    "Not Started": "bg-[#EC4899] text-gray-700",
    "In Progress": "bg-[#3B82F6] text-white",
    Completed: "bg-[#28A745] text-white",
    "On Hold": "bg-[#A855F7] text-white",
  };

  const priorityColors: Record<string, string> = {
    Urgent: "bg-red-600 text-white",
    High: "bg-orange-500 text-white",
    Medium: "bg-yellow-500 text-white",
    Low: "bg-stone-400 text-white",
  };

  const statusValue = (editable.status?.toString().trim() as
    | "Not Started"
    | "In Progress"
    | "Completed"
    | "On Hold") ?? "Not Started";

  const priorityValue = (editable.priority?.toString().trim() as
    | "Urgent"
    | "High"
    | "Medium"
    | "Low") ?? "Medium";

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold text-gray-800">{editable.name}</h1>
      </header>

      <section className="mx-auto w-full">
        <h2 className="text-lg font-semibold text-gray-700 mb-3">
          Project Description
        </h2>
        <p className="text-gray-600 leading-relaxed bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          {editable.description?.trim() || "No description provided for this project."}
        </p>
      </section>

      <section className="mx-auto w-full">
        <h2 className="text-lg sm:text-xl font-semibold text-gray-700 mb-4 sm:mb-6">
          Project Info
        </h2>

        <div className="bg-white rounded-xl border border-gray-200 p-4 sm:p-6 grid grid-cols-1 md:grid-cols-2 gap-6 sm:gap-8 shadow-lg">
          {/* Left Side */}
          <div className="space-y-5 sm:space-y-6 text-sm sm:text-base">
            <h3 className="text-base font-bold text-gray-500 border-b pb-2">
              General Info
            </h3>

            {/* Created At */}
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <SquarePen className="text-gray-500 w-4 h-4 sm:w-5 sm:h-5" />
                <span className="font-medium text-gray-700 whitespace-nowrap text-xs sm:text-sm">
                  Created At
                </span>
              </div>
              <p className="text-gray-500 text-xs sm:text-sm truncate">
                {editable.createdAt ? editable.createdAt.toDate().toLocaleDateString() : "—"}
              </p>
            </div>

            {/* Status */}
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <CheckCircle className="text-gray-500 w-4 h-4 sm:w-5 sm:h-5" />
                <span className="font-medium text-gray-700 whitespace-nowrap text-xs sm:text-sm">
                  Status
                </span>
              </div>
              <div className="relative w-[45%] sm:w-[50%]">
                <select
                  value={statusValue}
                  onChange={isReadOnly ? undefined : (e) => handleChange("status", e.target.value)}
                  disabled={isReadOnly}
                  className={`appearance-none w-full px-3 py-1 rounded-xl text-xs sm:text-sm font-medium border focus:outline-none focus:ring-1 focus:ring-blue-400
                    ${statusColors[statusValue]}
                    ${isReadOnly ? "cursor-not-allowed opacity-80" : ""}`}
                >
                  <option value="Not Started">Not Started</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Completed">Completed</option>
                  <option value="On Hold">On Hold</option>
                </select>
              </div>
            </div>

            {/* Priority */}
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Flag className="text-gray-500 w-4 h-4 sm:w-5 sm:h-5" />
                <span className="font-medium text-gray-700 whitespace-nowrap text-xs sm:text-sm">
                  Priority
                </span>
              </div>
              <div className="relative w-[45%] sm:w-[50%]">
                <select
                  value={priorityValue}
                  onChange={isReadOnly ? undefined : (e) => handleChange("priority", e.target.value)}
                  disabled={isReadOnly}
                  className={`appearance-none w-full px-3 py-1 rounded-xl text-xs sm:text-sm font-medium border focus:outline-none focus:ring-1 focus:ring-blue-400
                    ${priorityColors[priorityValue]}
                    ${isReadOnly ? "cursor-not-allowed opacity-80" : ""}`}
                >
                  <option value="Urgent">Urgent</option>
                  <option value="High">High</option>
                  <option value="Medium">Medium</option>
                  <option value="Low">Low</option>
                </select>
              </div>
            </div>
          </div>

          {/* Right Side */}
          <div className="space-y-5 sm:space-y-6 text-sm sm:text-base">
            <h3 className="text-base font-bold text-gray-500 border-b pb-2">
              Schedule Info
            </h3>

            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Calendar className="text-gray-500 w-4 h-4 sm:w-5 sm:h-5" />
                <span className="font-medium text-gray-700 whitespace-nowrap text-xs sm:text-sm">
                  Start Date
                </span>
              </div>
              <input
                type="date"
                value={editable.startDate || ""}
                onChange={(e) => handleChange("startDate", e.target.value)}
                disabled={isReadOnly}
                className={`border rounded-lg px-2 py-1 text-xs sm:text-sm w-[45%] sm:w-[50%] focus:outline-none focus:ring-1 focus:ring-blue-400
                  ${isReadOnly ? "bg-gray-100 cursor-not-allowed" : "bg-gray-50"}`}
              />
            </div>

            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Calendar className="text-gray-500 w-4 h-4 sm:w-5 sm:h-5" />
                <span className="font-medium text-gray-700 whitespace-nowrap text-xs sm:text-sm">
                  Due Date
                </span>
              </div>
              <input
                type="date"
                value={editable.dueDate || ""}
                onChange={(e) => handleChange("dueDate", e.target.value)}
                disabled={isReadOnly}
                className={`border rounded-lg px-2 py-1 text-xs sm:text-sm w-[45%] sm:w-[50%] focus:outline-none focus:ring-1 focus:ring-blue-400
                  ${isReadOnly ? "bg-gray-100 cursor-not-allowed" : "bg-gray-50"}`}
              />
            </div>

            <div className="flex items-center justify-between text-sm sm:text-base gap-4 sm:gap-6">
              <div className="flex items-center gap-2 flex-shrink-0">
                <Clock className="text-gray-500 w-5 h-5" />
                <span className="font-medium text-gray-700 whitespace-nowrap text-xs sm:text-sm">
                  Time Estimate
                </span>
              </div>
              <div className="flex justify-end w-40 sm:w-48">
                <p className="border rounded-lg px-2 py-1 text-xs sm:text-sm text-gray-700 bg-gray-50 text-center w-full whitespace-nowrap">
                  {editable.timeEstimate ? `${editable.timeEstimate} days` : "—"}
                </p>
              </div>
            </div>
          </div>
        </div>

        {!editable.startDate || !editable.dueDate ? (
          <div className="flex items-center mt-4 text-amber-600 text-sm bg-amber-50 border border-amber-200 p-3 rounded-lg shadow-sm">
            <AlertCircle className="w-5 h-5 mr-2" />
            <span>
              You haven’t set start and end dates yet. Setting them helps track progress in Calendar.
            </span>
          </div>
        ) : null}

        {error && (
          <div className="flex items-center mt-3 text-red-600 text-sm bg-red-50 border border-red-200 p-3 rounded-lg shadow-sm">
            <AlertCircle className="w-5 h-5 mr-2" />
            <span>{error}</span>
          </div>
        )}

        {!isReadOnly && (
          <div className="flex justify-end mt-6">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 sm:px-8 py-2.5 bg-gradient-to-r from-blue-600 to-blue-700 
               text-white font-semibold text-lg rounded-lg shadow-md hover:from-blue-700 
               hover:to-blue-800 transition-all duration-200 
               disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
