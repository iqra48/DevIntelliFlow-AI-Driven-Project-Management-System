"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { useAuth } from "@/context/AuthContext";
import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";
import WelcomeBanner from "@/components/welcomemsg";
import RecentProjects from "@/components/Recentprojects";
import CardGrid from "@/components/Cardgrids";
import Footer from "@/components/Footer";


const ProjectCreationModal = dynamic(
  () => import("@/components/ProjectCreationModal"),
  { ssr: false }
);

const ProjectsAreaChart = dynamic(() => import("@/components/Burnupchart"), {
  ssr: false,
  loading: () => <p className="text-gray-400">Loading chart...</p>,
});

const ChartProjectsStatus = dynamic(() => import("@/components/Donutchart"), {
  ssr: false,
  loading: () => <p className="text-gray-400">Loading chart...</p>,
});

export default function DashboardPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex flex-col min-h-screen">
      {/* Navbar */}
      <Navbar />

      <div className="flex flex-1">
        {/* Sidebar */}
        <Sidebar />

        {/* Main content */}
        <main
          className={`bg-[#F8F9FB]/90 flex-1 flex flex-col px-3 sm:px-6 md:px-8 pt-16 pb-10 transition-all duration-300
          ${isModalOpen ? "blur-sm" : ""} 
          ml-12 lg:ml-64`}
        >
          <div className="grid grid-cols-1 lg:grid-cols-6 gap-6">
            {/* Welcome Banner (full width) */}
            <div className="col-span-1 lg:col-span-6">
              <WelcomeBanner onCreateProject={() => setIsModalOpen(true)} />
            </div>

            {/* Row 1: CardGrid + Area Chart */}

            <div className="col-span-1 lg:col-span-2 flex">
              <div className="w-full h-full bg-[#F8F9FB]/90  p-0 pb-0 sm:p-0 sm:pb-0 flex">
                <CardGrid />
              </div>
            </div>

            <div className="col-span-1 lg:col-span-4 flex border-2 border-gray-200 ">
              <ProjectsAreaChart />
            </div>

            {/* Row 2: Recent Projects + Donut */}
            <div className="col-span-1 lg:col-span-4">
              <div className="w-full h-full bg-white  border-2 border-gray-200 shadow-xl p-4 sm:p-6 flex flex-col">
                <RecentProjects />
              </div>
            </div>

            <div className="col-span-1 lg:col-span-2 flex border-2 border-gray-200">
              <div className="w-full h-full min-h-[300px]">
                <ChartProjectsStatus />
              </div>
            </div>
          </div>
         
        </main>
        
      </div>
       <div className=" ml-12 lg:ml-64">
          <Footer />
          </div>

      {/* Modal */}
      {isModalOpen && (
        <ProjectCreationModal onClose={() => setIsModalOpen(false)} />
      )}
    </div>
  );
}
