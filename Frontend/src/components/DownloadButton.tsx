"use client";

import React, { useState, useRef, useEffect } from "react";
import { Download, FileText, FileSpreadsheet, FileType } from "lucide-react";
import {
  exportRequirementsAsCSV,
  exportRequirementsAsPDF,
  exportRequirementsAsDOCX,
} from "@/lib/exportRequirements";
import { FinalRequirement } from "@/lib/requirementApi";

interface DownloadButtonProps {
  requirements: FinalRequirement[];
  projectName: string;
  variant?: "button" | "icon"; // "button" = full button with text, "icon" = small icon only (for history)
}

export default function DownloadButton({
  requirements,
  projectName,
  variant = "button",
}: DownloadButtonProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleExport = async (format: "csv" | "pdf" | "docx") => {
    setOpen(false);
    if (!requirements.length) return;

    if (format === "csv") exportRequirementsAsCSV(requirements, projectName);
    else if (format === "pdf") exportRequirementsAsPDF(requirements, projectName);
    else if (format === "docx") await exportRequirementsAsDOCX(requirements, projectName);
  };

  return (
    <div className="relative" ref={containerRef}>
      {variant === "button" ? (
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="inline-flex items-center gap-2 rounded-lg border border-purple-200 bg-purple-50 px-4 py-2.5 text-sm font-semibold text-purple-700 transition hover:bg-purple-100"
        >
          <Download size={16} />
          Download
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="flex h-8 w-8 items-center justify-center rounded-md text-purple-700 hover:bg-purple-50"
          title="Download"
        >
          <Download size={16} />
        </button>
      )}

      {open && (
        <div className="absolute right-0 z-10 mt-2 w-44 rounded-lg border border-gray-200 bg-white shadow-lg">
          <button
            type="button"
            onClick={() => handleExport("pdf")}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
          >
            <FileText size={15} className="text-red-600" />
            PDF
          </button>
          <button
            type="button"
            onClick={() => handleExport("docx")}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
          >
            <FileType size={15} className="text-blue-600" />
            Word (.docx)
          </button>
          <button
            type="button"
            onClick={() => handleExport("csv")}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50"
          >
            <FileSpreadsheet size={15} className="text-green-600" />
            CSV
          </button>
        </div>
      )}
    </div>
  );
}