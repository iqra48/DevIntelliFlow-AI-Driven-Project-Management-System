"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Folder, House, Calendar, User } from "lucide-react";
import { Project } from "@/types/project";

type Props = {
  projects: Project[];
  onSearch?: (items: Project[]) => void;
};

const APP_PAGES = [
  {
    id: "dashboard",
    label: "Dashboard",
    path: "/dashboard",
    icon: House,
  },
  {
    id: "projects",
    label: "Projects",
    path: "/projects",
    icon: Folder,
  },
  {
    id: "calender", 
    label: "Calender",
    path: "/calender", 
    icon: Calendar,
  },
  {
    id: "profile",
    label: "Profile",
    path: "/userprofile", 
    icon: User,
  },
];

export default function NavbarSearch({ projects }: Props) {
  const router = useRouter();
  const [query, setQuery] = useState("");

  const trimmedQuery = query.trim().toLowerCase();

  const pageResults = APP_PAGES.filter((p) =>
    p.label.toLowerCase().includes(trimmedQuery)
  );

  const projectResults = projects.filter((p) =>
    p.name.toLowerCase().includes(trimmedQuery)
  );

  const hasAnyResults =
    trimmedQuery.length > 0 &&
    (pageResults.length > 0 || projectResults.length > 0);

  return (
    <div className="relative w-48 sm:w-64">
      {/* Search input */}
      <div className="flex items-center bg-white/10 rounded-full px-3 py-1.5 focus-within:ring-2 focus-within:ring-purple-600">
        <Search size={16} className="text-gray-300 mr-2 shrink-0" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search..."
          className="bg-transparent w-full text-sm text-white placeholder-gray-300 focus:outline-none"
        />
      </div>

      {/* Dropdown */}
      {query && (
        <div className="absolute mt-2 w-full z-50 bg-white rounded-lg shadow-lg overflow-hidden">
          {/* Pages */}
          {pageResults.length > 0 && (
            <div className="border-b">
              <p className="px-3 py-1 text-xs font-semibold text-gray-400">
                Pages
              </p>
              {pageResults.map((page) => {
                const Icon = page.icon;
                return (
                  <button
                    key={page.id}
                    onClick={() => {
                      router.push(page.path);
                      setQuery("");
                    }}
                    className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-800 hover:bg-gray-100"
                  >
                    <Icon size={14} />
                    {page.label}
                  </button>
                );
              })}
            </div>
          )}

          {/* Projects */}
          {projectResults.length > 0 && (
            <div>
              <p className="px-3 py-1 text-xs font-semibold text-gray-400">
                Projects
              </p>
              {projectResults.map((proj) => (
                <button
                  key={proj.id}
                  onClick={() => {
                    router.push(`/projects/${proj.id}`);
                    setQuery("");
                  }}
                  className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-800 hover:bg-gray-100 truncate"
                >
                  <Folder size={14} />
                  {proj.name}
                </button>
              ))}
            </div>
          )}

          {/* No results */}
          {!hasAnyResults && (
            <div className="px-4 py-3 text-sm text-gray-500 text-center">
              No results found
            </div>
          )}
        </div>
      )}
    </div>
  );
}
