"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Project } from "@/types/project";

export function useProjectSearch(
  projects: Project[],
  onSearch: (items: Project[]) => void
) {
  const [input, setInput] = useState("");
  const [options, setOptions] = useState<Project[]>([]);
  const router = useRouter();

  const updateQuery = (text: string) => {
    setInput(text);

    if (!text.trim()) {
      setOptions([]);
      onSearch(projects);
      return;
    }

    const matches = projects.filter((p) =>
      p.name.toLowerCase().includes(text.toLowerCase())
    );

    setOptions(matches.slice(0, 5));
    onSearch(matches);
  };

  const handleSearch = () => {
    if (!input.trim()) return;

    const exact = projects.find(
      (p) => p.name.toLowerCase() === input.toLowerCase()
    );

    if (exact) {
      onSearch([exact]);
      setOptions([]);
    }
  };

  const jumpToProject = (id: string) => {
    router.push(`/projects/${id}`);
  };

  return { input, setInput, options, updateQuery, handleSearch, jumpToProject };
}
