"use client";

import {
  Database,
  SlidersHorizontal, 
  Lock,
  BotMessageSquare,
  User,
  Cookie,
  RefreshCcw,
} from "lucide-react";
import Footer from "@/components/Footer";
import Image from "next/image";
import Navbar from "@/components/Navbar";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

const sections = [
  {
    icon: Database,
    title: "Data We Collect",
    content: [
      "Personal Data: Name, email address, and profile details provided during account creation.",
      "Project Data: All projects, requirements, and metrics you save in Firestore.",
      "AI Input Data: Requirements you send for AI classification or test case generation.",
      "Technical Data: IP address, browser type, and app usage activity logs.",
    ],
  },
  {
    icon:  SlidersHorizontal, 
    title: "How We Use Your Data",
    content: [
      "To manage your account and provide login access.",
      "To analyze your requirements and generate test cases via our AI engine.",
      "To improve system performance and fix bugs.",
      "To send you important updates and notifications.",
    ],
  },
  {
    icon: Lock,
    title: "Data Storage & Security",
    content: [
      "All data is stored on encrypted Google Firebase servers, one of the most secure cloud infrastructures.",
      "Data is protected in transit and at rest using SSL/TLS encryption.",
      "Only you (or people you share links with) can access your project data.",
    ],
  },
  {
    icon: BotMessageSquare,
    title: "AI & Third-Party Services",
    content: [
      "AI models process your data solely for generating classifications or test cases. We never sell your data.",
      "Authentication uses Google Login, subject to Google's privacy policy.",
    ],
  },
  {
    icon: User,
    title: "Your Rights",
    content: [
      "Edit: Update profile and project data anytime.",
      "Delete: Permanently remove your account or projects; data is immediately deleted from Firestore.",
      "Export: Download any generated test cases for your use.",
    ],
  },
  {
    icon: Cookie,
    title: "Cookies",
    content: [
      "Cookies are used only to maintain login sessions and improve website performance.",
      "We do not track your browser history or other personal activities.",
    ],
  },
  {
    icon: RefreshCcw,
    title: "Changes to Privacy Policy",
    content: [
      "We may update this privacy policy periodically.",
      "Significant changes will be communicated via email or dashboard notifications.",
      "Continued use of the platform implies acceptance of updated policies.",
    ],
  },
];

export default function PrivacyPage() {
    
  return (
    <div className="flex min-h-screen flex-col bg-gray-50 text-gray-900">
        <Navbar />
      <main className="flex-1">
      {/* Header */}
<section className="border-b border-gray-200 bg-gray-200 mt-10 relative">
  {/* Back button - positioned relative to the page */}
  <Link
    href="/dashboard"
    className="fixed left-6 top-32 transform -translate-y-1/2 flex items-center justify-center w-12 h-12 bg-gray-400 rounded-full hover:bg-indigo-700 transition-colors z-50"
  >
    <ArrowLeft className="h-6 w-6 text-white" />
  </Link>

  {/* Main centered header */}
  <div className="mx-auto max-w-6xl px-6 py-12 flex flex-col md:flex-row items-center gap-6">
    <Image
      src="/shield.png"
      alt="Privacy Icon"
      width={80}
      height={80}
    />
    <div className="flex-1 text-center md:text-left">
      <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
        Privacy Policy
      </h1>
      <p className="mt-2 text-gray-500 text-sm md:text-base">
        Last updated: December 2025
      </p>
    </div>
  </div>
</section>



        {/* Content */}
        <section className="mx-auto max-w-6xl px-6 py-16 space-y-12">
          {sections.map((section, idx) => {
            const Icon = section.icon;
            return (
              <div
                key={idx}
                className="rounded-2xl border border-gray-200 bg-white p-10 shadow-lg hover:shadow-xl transition-shadow duration-300"
              >
                <div className="flex items-center gap-3 mb-6">
                  <Icon className="h-7 w-7 text-indigo-600" />
                  <h2 className="text-2xl md:text-3xl font-semibold">
                    {section.title}
                  </h2>
                </div>
                <ul className="space-y-4 text-lg text-gray-700 leading-relaxed">
                  {section.content.map((item, i) => (
                    <li key={i} className="list-disc ml-8">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </section>
      </main>

      <Footer />
    </div>
  );
}
