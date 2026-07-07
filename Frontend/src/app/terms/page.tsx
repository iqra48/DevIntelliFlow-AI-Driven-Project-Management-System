"use client";

import {
  ShieldCheck,
  User,
  Sparkles,
  Database,
  Ban,
  AlertTriangle,
  Link as LinkIcon,
  RefreshCcw,
} from "lucide-react";
import Footer from "@/components/Footer";
import Image from "next/image";
import Navbar from "@/components/Navbar";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
const sections = [
  {
    icon: User,
    title: "Account & Security",
    content: [
      "You are responsible for maintaining the confidentiality of your account credentials.",
      "All activities performed under your account are your sole responsibility.",
      "You must provide accurate and complete information during registration.",
      "We reserve the right to suspend accounts involved in misuse without prior notice.",
    ],
  },
  {
    icon: Sparkles,
    title: "Use of AI Features",
    content: [
      "AI-generated classifications and test cases are provided for guidance only.",
      "We do not guarantee 100% accuracy of AI outputs.",
      "You are responsible for reviewing and validating all AI-generated results before use.",
    ],
  },
  {
    icon: Database,
    title: "User Data & Privacy",
    content: [
      "You retain full ownership of all projects and data you upload.",
      "DevIntelliFlow does not claim ownership over your content.",
      "All data is stored securely using Google Firebase infrastructure.",
      "We do not sell or share your personal data with third parties.",
    ],
  },
  {
    icon: Ban,
    title: "Prohibited Activities",
    content: [
      "Attempting to breach or bypass system security.",
      "Reverse engineering, copying, or exploiting the platform.",
      "Uploading illegal, abusive, or hateful content.",
      "Excessive or abusive usage of system resources or APIs.",
    ],
  },
  {
    icon: AlertTriangle,
    title: "Limitation of Liability",
    content: [
      "Service availability is not guaranteed at all times.",
      "We are not liable for data loss, downtime, or business damages.",
      "Use of DevIntelliFlow is at your own risk.",
    ],
  },
  {
    icon: LinkIcon,
    title: "Shareable Links",
    content: [
      "View-only links can be accessed by anyone with the link.",
      "You are responsible for sharing links securely.",
      "DevIntelliFlow is not responsible for misuse of shared links.",
    ],
  },
  {
    icon: RefreshCcw,
    title: "Changes to Terms",
    content: [
      "We may update these terms from time to time.",
      "Significant changes will be communicated via email or dashboard notifications.",
      "Continued use of the platform implies acceptance of updated terms.",
    ],
  },
];

export default function TermsPage() {
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
          src="/terms_logo.png"
          alt="Term Icon"
          width={80}
          height={80}
        />
        <div className="flex-1 text-center md:text-left">
          <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
            Terms & Conditions
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
                className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm"
              >
                <div className="flex items-center gap-3 mb-4">
                  <Icon className="h-6 w-6 text-indigo-600" />
                  <h2 className="text-2xl font-semibold">{section.title}</h2>
                </div>
                <ul className="space-y-3 text-base text-gray-700 leading-relaxed">
                  {section.content.map((item, i) => (
                    <li key={i} className="list-disc ml-6">
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
