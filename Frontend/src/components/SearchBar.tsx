"use client";

import { Search } from "lucide-react";
import { Project } from "@/types/project";
import { useState } from "react";
import { useRouter } from "next/navigation";

type Props = {
  projects: Project[];
  onSearch: (filtered: Project[], query: string) => void;
  placeholder?: string;
};

export default function SearchBar({
  projects,
  onSearch,
  placeholder = "Search projects...",
}: Props) {
  const [input, setInput] = useState("");
  const [options, setOptions] = useState<Project[]>([]);
  const router = useRouter();

  const updateQuery = (value: string) => {
    setInput(value);

    if (value.trim() === "") {
      setOptions([]);
      onSearch(projects, "");
      return;
    }

    const filtered = projects.filter((proj) =>
      proj.name.toLowerCase().includes(value.toLowerCase())
    );

    setOptions(filtered);
    onSearch(filtered, value);
  };

  const handleSearch = () => {
    const filtered = projects.filter((proj) =>
      proj.name.toLowerCase().includes(input.toLowerCase())
    );

    setOptions(filtered);
    onSearch(filtered, input);
  };

  // ✅ FIXED
  const jumpToProject = (id: string) => {
    router.push(`/projects/${id}`);
  };

  return (
    <div className="relative w-full max-w-md lg:max-w-xl">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSearch();
        }}
        className="flex items-center bg-white border-2 rounded-full overflow-hidden shadow-sm focus-within:ring-2 focus-within:ring-purple-600"
      >
        <Search size={18} className="ml-3 text-gray-400" />

        <input
          type="text"
          value={input}
          onChange={(e) => updateQuery(e.target.value)}
          placeholder={placeholder}
          className="flex-grow px-3 py-2 text-sm text-gray-700 focus:outline-none"
        />

        <button
          type="submit"
          className="bg-purple-600 text-white px-5 py-2 text-sm font-medium rounded-full hover:bg-purple-700 transition"
        >
          Search
        </button>
      </form>

      {/* Dropdown */}
      {input.trim() !== "" && options.length > 0 && (
        <div className="absolute mt-1 w-full z-50 bg-white border rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {options.map((proj) => (
            <button
              key={proj.id}
              type="button"
              onClick={() => jumpToProject(proj.id)}
              className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100"
            >
              {proj.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
