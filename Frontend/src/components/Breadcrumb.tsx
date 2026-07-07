"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { doc, getDoc } from "firebase/firestore";
import { db } from "@/firebase/firebaseConfig";

const Breadcrumb = () => {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  const [projectName, setProjectName] = useState<string>("Project");

  useEffect(() => {
    
    if (segments[0] === "projects" && segments[1]) {
      const fetchProjectName = async () => {
        try {
          const snap = await getDoc(doc(db, "projects", segments[1]));
          if (snap.exists()) {
            setProjectName(snap.data().name);
          }
        } catch (err) {
          console.error("Failed to fetch project name", err);
        }
      };

      fetchProjectName();
    }
  }, [segments]);

  const breadcrumbMap: Record<string, string> = {
    projects: "Projects",
    requirement_page: "Requirements",
    testcase: "Testcases",
    metric_cal: "Metric Calculator",
    setting: "Settings",
  };

  const items = [
    { href: "/dashboard", name: "Dashboard" },
    ...segments.map((segment, index) => {
      const href = "/" + segments.slice(0, index + 1).join("/");

      // Project name slot
      if (index === 1 && segments[0] === "projects") {
        return { href, name: projectName };
      }

      const name = breadcrumbMap[segment] || "Overview";
      return { href, name };
    }),
  ];

  return (
    <nav className="flex space-x-2 text-sm">
      {items.map((item, index) => (
        <span key={item.href} className="flex items-center">
          <Link
            href={item.href}
            className="text-gray-500 hover:underline italic hover:text-gray-700 hover:font-semibold"
          >
            {item.name}
          </Link>
          {index < items.length - 1 && <span className="mx-2">{">>"}</span>}
        </span>
      ))}
    </nav>
  );
};

export default Breadcrumb;
