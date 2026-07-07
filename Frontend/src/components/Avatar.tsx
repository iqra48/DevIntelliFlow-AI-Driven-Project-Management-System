"use client";

import React, { useMemo } from "react";

interface AvatarProps {
  name?: string;
  email?: string;
  size?: string; // w-12 h-12 or w-16 h-16
}

const colors = [
  "bg-indigo-700",
  "bg-blue-gray-500",
  "bg-slate-700",
  "bg-teal-600",
  "bg-stone-700",
  "bg-neutral-600",
  "bg-brown-600",
];

export default function Avatar({ name, email, size = "w-16 h-16" }: AvatarProps) {
  // Compute initials
 const initials = useMemo(() => {
  if (name?.trim()) {
    const parts = name.trim().split(" ").filter(Boolean);
    if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    if (parts[0]) return parts[0][0].toUpperCase();
  } else if (email?.trim()) {
    return email[0].toUpperCase();
  }
  return "?";
}, [name, email]);

  // Compute color
  const color = useMemo(() => {
    const base = (email || name || "x").charCodeAt(0);
    return colors[base % colors.length];
  }, [name, email]);

  return (
    <div
      className={`
        ${size} ${color} 
        rounded-full flex items-center justify-center  text-white font-bold text-xl transition-all duration-500 ease-in-out
      `}
    >
      {initials}
    </div>
  );
}
