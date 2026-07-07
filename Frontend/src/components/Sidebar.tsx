"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  X,
  PanelRightClose,
  House,
  FolderClosed,
  LogOut,
  CalendarDays,
  UserCog,
} from "lucide-react";

export default function Sidebar() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();

  const menuItems = [
    { label: "Dashboard", href: "/dashboard", icon: <House size={18} /> },
    { label: "Projects", href: "/projects", icon: <FolderClosed size={18} /> },
    { label: "Calender", href: "/calender", icon: <CalendarDays size={18} /> },
    {label: "Profile", href:"/userprofile", icon:<UserCog size={18} />},
  ];

  return (
    <>
      {/* Narrow vertical strip  */}
      {!isOpen && (
        <div className="lg:hidden fixed top-14 left-0 h-[calc(100%-56px)] w-12 bg-white shadow-md flex flex-col items-center z-40">
          <button
            onClick={() => setIsOpen(true)}
            className="mt-4 p-2 rounded-md hover:bg-gray-100"
          >
            <PanelRightClose size={20} />
          </button>
        </div>
      )}

      {/* Sidebar with animation */}
      <aside
        className={`fixed left-0 w-64 bg-white text-black shadow-lg z-50
  transform transition-transform duration-300 ease-in-out
  ${isOpen ? "translate-x-0 top-14 h-[calc(100%-56px)]" : "-translate-x-full"} 
  lg:translate-x-0 lg:top-14 lg:h-[calc(100%-56px)]`}
      >
        <div className="flex flex-col h-full">
          {/* Close button on mobile*/}
          <div className="flex justify-end lg:hidden p-2 border-b">
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 rounded-md hover:bg-gray-100"
            >
              <X size={18} />
            </button>
          </div>

          {/* Menu */}
          <nav className="flex-1 p-4 space-y-2">
            {menuItems.map((item, idx) => (
              <Link
                key={idx}
                href={item.href}
                className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors ${
                  pathname === item.href
                    ? "bg-purple-100 text-purple-700 font-semibold"
                    : "hover:bg-gray-200"
                }`}
              >
                {item.icon}
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="p-4 border-t border-gray-200">
            <Link
              href="/logout"
              className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors ${
                pathname === "/logout"
                  ? "text-blue hover:bg-gray-200 font-semibold"
                  : "text-blue-600  hover:bg-gray-200 "
              }`}
            >
              <LogOut size={18} />
              <span>Logout</span>
            </Link>
          </div>
        </div>
      </aside>

      {/* Dark overlay (mobile only) */}
      {isOpen && (
        <div
          onClick={() => setIsOpen(false)}
          className="fixed inset-0 bg-black/50 lg:hidden z-40 transition-opacity duration-300 ease-in-out"
        />
      )}
    </>
  );
}
