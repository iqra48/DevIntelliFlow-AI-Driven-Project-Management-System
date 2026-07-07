"use client";

import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";
import ProfileForm from "@/components/ProfileForm";
import { useState, useEffect } from "react";

export default function ProfilePage() {
  const [sidebarState, setSidebarState] = useState<"none" | "narrow" | "full">("none");

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const overlay = document.querySelector(".bg-black\\/50");
      const narrowSidebar = document.querySelector(".w-12.bg-white.shadow-md");

      if (overlay) {
        setSidebarState("full");
      } else if (narrowSidebar) {
        setSidebarState("narrow");
      } else {
        setSidebarState("none");
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  const paddingLeft =
    sidebarState === "full"
      ? "pl-64"
      : sidebarState === "narrow"
      ? "pl-12"
      : "pl-0";

  return (
    <div className="flex flex-col h-screen">
      <Navbar />

      <div className="relative flex flex-1 bg-gradient-to-r from-pink-100 to-blue-100 pt-[72px] overflow-hidden">
        <Sidebar />
<main
  className={`
    flex-1 flex justify-center items-start 
    px-4 sm:px-6 py-6 sm:py-10 overflow-y-auto 
    transition-all duration-300 ease-in-out

    ${sidebarState === "full" ? "lg:pl-[calc(16rem+1.5rem)]" : ""}
    ${sidebarState === "narrow" ? "pl-[calc(3rem+0.75rem)] md:pl-[calc(3rem+1.5rem)] lg:pl-[calc(16rem+1.5rem)]" : ""}
    ${sidebarState === "none" ? "pl-0" : ""}
  `}
>
  <div className="w-full max-w-3xl mx-auto">
    <ProfileForm />
  </div>
</main>


      </div>
    </div>
  );
}
