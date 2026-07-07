"use client";

import Image from "next/image";
import { Playfair_Display } from "next/font/google";
import { motion } from "@/lib/motion";

const playfair = Playfair_Display({
  weight: "700",
  subsets: ["latin"],
});

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex flex-col items-center justify-center min-h-screen overflow-hidden  bg-white">
      {/* Background Layer */}
      <Image
        src="/waveblob.png"
        alt="Background"
        fill
        priority
        className="object-cover object-center"
      />
      <div className="absolute inset-0 bg-gradient-to-b from-purple-200 to-white/10 backdrop-blur-[2px]" />

      {/* Logo + Name */}
     <motion.div
  initial={{ opacity: 0, y: -15 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.6, ease: "easeOut" }}
  className="
    flex flex-col items-center justify-center
    lg:flex-row lg:items-center lg:justify-start
    text-center lg:text-left
    gap-2 lg:gap-3
    z-30
    mt-[clamp(1.5rem,4vh,3rem)]
    lg:absolute lg:top-[0.25rem] lg:left-[1.25rem]
  "
>
  <Image
    src="/color_logo1.png"
    alt="App Logo"
    width={80}
    height={80}
    
  />
  <h1
    className={`${playfair.className} text-2xl sm:text-3xl font-extrabold text-gray-800 drop-shadow-lg`}
  >
    DevIntelliFlow
  </h1>
</motion.div>



      {/* Page Content / Form Section */}
      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
          className="
    relative z-20 flex items-center justify-center
    w-full px-4 sm:px-6 md:px-8
    pt-16 lg:pt-28
    pb-16
  "
>
        {children}
      </motion.div>
    </div>
  );
}
