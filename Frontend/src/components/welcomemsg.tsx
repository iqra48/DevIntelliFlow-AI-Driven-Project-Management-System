"use client";

import { useEffect, useState } from "react";
import { getAuth, onAuthStateChanged, User } from "firebase/auth";
import Image from "next/image";
import { FolderPlus } from "lucide-react";

interface WelcomeBannerProps {
  onCreateProject: () => void;
}

const WelcomeBanner = ({ onCreateProject }: WelcomeBannerProps) => {
  const [name, setName] = useState<string>("");

  useEffect(() => {
    const auth = getAuth();

    const unsubscribe = onAuthStateChanged(auth, (currentUser: User | null) => {
      if (currentUser) {
        const resolvedName =
          currentUser.displayName ??
          (currentUser.email ? currentUser.email.split("@")[0] : "User");
        setName(resolvedName);
      } else {
        setName("Guest");
      }
    });

    return () => unsubscribe();
  }, []);

  return (
    <section className="mt-3 mb-2">
      <div className="relative w-full shadow-xl overflow-hidden h-[270px] sm:h-[220px] md:h-[270px]">
        {/* Background Image */}
        <Image
          src="/banner.png"
          alt="workflow illustration"
          fill
          className="object-cover object-right"
          priority
        />

        {/* Left gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-r from-white via-white/90 to-transparent" />

        {/* Text Content */}
        <div className="relative z-10 h-full flex flex-col justify-center px-6 md:px-8 max-w-lg md:max-w-2xl lg:max-w-3xl pb-6 xs:pb-8">
          <h1
            className="
    text-[clamp(2rem,4vw,3.25rem)] font-bold text-gray-900 leading-tight
    whitespace-normal md:whitespace-nowrap
  "
          >
            Welcome back,{" "}
            <span className="text-purple-700 block md:inline">{name}</span>
          </h1>

          <p className="text-[clamp(0.9rem,2vw,1.125rem)] text-gray-700 mt-2">
            Here’s what’s happening with your projects today.
          </p>

          <div className="mt-3 h-1 w-28 rounded bg-gradient-to-r from-purple-400 to-blue-400"></div>

          <button
            onClick={onCreateProject}
            className="mt-7 w-fit flex items-center justify-center rounded-lg bg-gradient-to-r from-purple-800 to-purple-700 
        hover:from-purple-600 hover:to-purple-500 shadow-md px-6 py-3 
        text-[clamp(0.9rem,1.5vw,1rem)] font-semibold text-white 
        whitespace-nowrap transition-transform transform hover:scale-105 active:scale-95"
          >
            <FolderPlus className="w-5 h-5 mr-2 shrink-0" />
            Create Project
          </button>
        </div>
      </div>
    </section>
  );
};

export default WelcomeBanner;
