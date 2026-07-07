"use client";

import React, { useEffect, useState } from "react";
import { Loader2, Clock, FileText } from "lucide-react";
import {
  getRequirementHistory,
  RequirementHistoryEntry,
} from "@/lib/requirementApi";
import DownloadButton from "@/components/DownloadButton";

interface RequirementHistoryListProps {
  projectId: string;
  projectName: string;
}

export default function RequirementHistoryList({
  projectId,
  projectName,
}: RequirementHistoryListProps) {
  const [history, setHistory] = useState<RequirementHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await getRequirementHistory(projectId);
        setHistory(data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="animate-spin text-purple-600" size={28} />
      </div>
    );
  }

  if (!history.length) {
    return (
      <p className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-500">
        No requirement generation history yet.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {history.map((entry) => {
        const isOpen = expandedId === entry.id;
        const date = entry.generatedAt?.toDate
          ? entry.generatedAt.toDate().toLocaleString()
          : "Unknown date";

        return (
          <div
            key={entry.id}
            className="rounded-lg border border-gray-200 bg-white shadow-sm"
          >
            <div className="flex w-full items-center justify-between p-4">
              <button
                type="button"
                onClick={() => setExpandedId(isOpen ? null : entry.id)}
                className="flex flex-1 items-center gap-3 text-left"
              >
                <Clock size={16} className="text-purple-600" />
                <div>
                  <p className="text-sm font-semibold text-gray-800">{date}</p>
                  <p className="text-xs text-gray-500">
                    {entry.requirements.length} requirements generated
                    {entry.fileName ? ` • from ${entry.fileName}` : ""}
                  </p>
                </div>
              </button>

              <div className="flex items-center gap-2">
                <DownloadButton
                  requirements={entry.requirements}
                  projectName={projectName}
                  variant="icon"
                />
                <button
                  type="button"
                  onClick={() => setExpandedId(isOpen ? null : entry.id)}
                  className="text-xs font-medium text-purple-700"
                >
                  {isOpen ? "Hide" : "View"}
                </button>
              </div>
            </div>

            {isOpen && (
              <div className="border-t border-gray-100 p-4 space-y-3">
                {entry.inputText && (
                  <div className="flex items-start gap-2 text-xs text-gray-500">
                    <FileText size={14} className="mt-0.5 shrink-0" />
                    <p className="line-clamp-3">{entry.inputText}</p>
                  </div>
                )}
                {entry.requirements.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-md border border-gray-100 bg-gray-50 p-3 text-sm text-gray-700"
                  >
                    <span className="mr-2 rounded bg-purple-100 px-2 py-0.5 text-xs font-semibold text-purple-700">
                      {item.classification_type}
                    </span>
                    {item.requirement}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}