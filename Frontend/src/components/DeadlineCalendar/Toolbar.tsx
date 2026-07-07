"use client";

import { ToolbarProps, View } from "react-big-calendar";
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon } from "lucide-react";

export default function CustomToolbar({
  label,
  onNavigate,
  onView,
  view, 
}: ToolbarProps) {
  return (
    <div className="flex flex-col sm:flex-row items-center justify-between mb-4 gap-3">
      {/* Month Heading */}
      <div className="flex items-center gap-2 text-lg font-semibold text-gray-800">
        <CalendarIcon className="w-5 h-5 text-purple-600" />
        <span>{label}</span>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => onNavigate("TODAY")}
          className="px-3 py-1.5 text-sm font-medium bg-purple-600 text-white rounded-lg shadow hover:bg-purple-700 transition"
        >
          Today
        </button>
        <button
          onClick={() => onNavigate("PREV")}
          className="p-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 transition"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        <button
          onClick={() => onNavigate("NEXT")}
          className="p-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 transition"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Views */}
      <div className="flex gap-2">
        {(["month", "week", "day"] as View[]).map((v) => {
          const isActive = v === view; //  check active view
          return (
            <button
              key={v}
              onClick={() => onView(v)}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg border transition
                ${
                  isActive
                    ? "bg-purple-600 text-white border-purple-600 shadow"
                    : "border-gray-300 text-gray-700 hover:bg-purple-100 hover:border-purple-400"
                }`}
            >
              {v.charAt(0).toUpperCase() + v.slice(1)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
