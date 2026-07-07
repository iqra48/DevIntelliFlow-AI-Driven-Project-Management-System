"use client";

import Navbar from "@/components/Navbar";
import ProjectSidebar from "@/components/ProjectSidebar";
import Breadcrumb from "@/components/Breadcrumb";

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-col h-screen">
      <Navbar />
      <div className="flex flex-1">
        <ProjectSidebar />
        <main className="flex-1 px-6 pt-16 pb-10 lg:ml-64 ml-12 overflow-y-auto bg-[#F8F9FB]/90">
          {/* Breadcrumb */}
          <Breadcrumb />

          {/* Page  content */}
          <div className="mt-4 bg-[#F8F9FB]/90">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
