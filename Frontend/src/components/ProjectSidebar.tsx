"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ListChecks,
  ClipboardCheck,
  ChartNoAxesColumn,
  Settings,
} from "lucide-react";

const navItems = [
  { name: "Overview", href: "", icon: LayoutDashboard },
  { name: "Requirements", href: "/requirement_page", icon: ListChecks },
  { name: "Testcases", href: "/testcase", icon: ClipboardCheck },
  { name: "Metric Calculator", href: "/metric_cal", icon: ChartNoAxesColumn },
  { name: "Settings", href: "/setting", icon: Settings },
];

export default function ProjectSidebar() {
  const { id } = useParams();
  const pathname = usePathname();

  return (
    <>
      {/* Full Sidebar for lg and up*/}
      <aside className="hidden lg:block fixed top-14 left-0 h-[calc(100vh-3.5rem)] w-64 text-gray-900 bg-white shadow-2xl p-6">
        <h2 className="font-bold text-lg pb-3 mb-4 border-b border-purple-600 shadow-2xl">
          Workspace
        </h2>

        <nav className="space-y-2">
          {navItems.map((item) => {
            const href = `/projects/${id}${item.href}`;
            const active =
              pathname === href ||
              (pathname === `/projects/${id}` && item.href === "");
            const Icon = item.icon;

            return (
              <Link
                key={item.name}
                href={href}
                className={`flex items-center gap-3 px-4 py-2 rounded-lg transition ${
                  active ? "bg-purple-700 text-white" : "hover:bg-blue-100"
                }`}
              >
                <Icon size={18} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Compact Sidebar (sm–md only) */}
      <aside className="block lg:hidden fixed top-14 left-0 h-[calc(100vh-3.5rem)] w-14 text-gray-900 bg-white shadow-2xl">
        <nav className="flex flex-col items-center py-4 space-y-6">
          {navItems.map((item) => {
            const href = `/projects/${id}${item.href}`;
            const active =
              pathname === href ||
              (pathname === `/projects/${id}` && item.href === "");
            const Icon = item.icon;

            return (
              <Link
                key={item.name}
                href={href}
                className={`flex items-center justify-center w-10 h-10 rounded-lg transition ${
                  active ? "bg-purple-700 text-white" : "hover:bg-blue-100"
                }`}
                title={item.name} // tooltip on hover
              >
                <Icon size={20} />
              </Link>
            );
          })}
        </nav>
      </aside>
    </>
  );
}
