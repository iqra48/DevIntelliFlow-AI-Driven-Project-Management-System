import React from "react";
import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-white border-t  border-gray-200  shadow-[0_-4px_10px_rgba(0,0,0,0.1)]">
      <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col md:flex-row items-center justify-between text-sm text-gray-500">
        
        {/* Brand + copyright */}
        <p className="text-center md:text-left">
          © {new Date().getFullYear()}{" "}
          <span className="font-semibold bg-gradient-to-r from-purple-700 via-pink-500 to-blue-600 bg-clip-text text-transparent">
            DevIntelliFlow
          </span>. All rights reserved.
        </p>

        {/* Links */}
        <div className="flex space-x-6 mt-3 md:mt-0">
          <Link href="/terms" className="hover:text-blue-600 transition">Terms</Link>
          <Link href="/privacy" className="hover:text-blue-600 transition">Privacy</Link>
          <Link href="/help" className="hover:text-blue-600 transition">Help</Link>
        </div>
      </div>
    </footer>
  );
}
