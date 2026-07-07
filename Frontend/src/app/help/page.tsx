"use client";

import Image from "next/image";
import {
  Rocket,
  FolderKanban,
  Sparkles,
  BarChart3,
  User,
  HelpCircle,
  ArrowLeft,
} from "lucide-react";
import Footer from "@/components/Footer";
import Navbar from "@/components/Navbar";
import Link from "next/link";

export default function HelpPage() {
  return (
    <div className="flex min-h-screen flex-col bg-gray-50 text-gray-900">
      <Navbar />

      <main className="flex-1">
        {/* Header */}
        <section className="border-b border-gray-200 bg-gray-200 mt-10 relative">
          {/* Back button */}
          <Link
            href="/dashboard"
            className="fixed left-6 top-32 transform -translate-y-1/2 flex items-center justify-center w-12 h-12 bg-gray-400 rounded-full hover:bg-indigo-700 transition-colors z-50"
          >
            <ArrowLeft className="h-6 w-6 text-white" />
          </Link>

          {/* Main header content */}
          <div className="mx-auto max-w-6xl px-6 py-12 flex flex-col md:flex-row items-center gap-6">
            <Image
              src="/help_icon.png"
              alt="DevIntelliFlow Logo"
              width={80}
              height={80}
            />
            <div className="flex-1 text-center md:text-left">
              <h1 className="text-3xl md:text-4xl font-bold tracking-tight">
                DevIntelliFlow Help Center
              </h1>
              <p className="mt-2 text-gray-500 text-sm md:text-base">
                Learn how to use DevIntelliFlow efficiently and understand every feature.
              </p>
            </div>
          </div>
        </section>

        {/* Help Content */}
        <div className="mx-auto max-w-7xl px-8 py-16 space-y-16">
          {/* Getting Started */}
          <HelpSection icon={Rocket} title="Getting Started">
            <SubTitle title="Create an Account" />
            <List>
              <li>
                <strong>Sign Up:</strong> Enter your name, email, and password on
                the Sign Up page.
              </li>
              <li>
                <strong>Google Sign-In:</strong> Register instantly using your
                Google account.
              </li>
              <li>
                <strong>Login:</strong> Existing users can log in and will be
                redirected to the Dashboard.
              </li>
            </List>

            <SubTitle title="Understanding the Dashboard" />
            <List>
              <li>
                <strong>Summary Cards:</strong> View Active, Completed, Overdue,
                and High Priority projects.
              </li>
              <li>
                <strong>Progress Chart:</strong> Visual overview of created and
                completed projects.
              </li>
              <li>
                <strong>Recent Projects:</strong> Quickly access your latest
                projects.
              </li>
            </List>
          </HelpSection>

          {/* Project Management */}
          <HelpSection icon={FolderKanban} title="Project Management">
            <SubTitle title="Create a New Project" />
            <ol className="list-decimal space-y-3 pl-6 text-lg text-gray-700">
              <li>Open the Projects section from the side menu.</li>
              <li>
                Click <strong>Start New Project</strong>.
              </li>
              <li>
                Enter project name, description, priority, and status.
              </li>
              <li>Save to create the project.</li>
            </ol>

            <SubTitle title="Project Settings & Sharing" />
            <List>
              <li>Edit project details anytime from Settings.</li>
              <li>
                Generate a <strong>view-only shareable link</strong> for clients or
                team members.
              </li>
              <li>Delete projects permanently when no longer required.</li>
            </List>
          </HelpSection>

          {/* AI Features */}
          <HelpSection icon={Sparkles} title="AI-Powered Features">
            <SubTitle title="AI Requirements Classification" />
            <List>
              <li>Enter requirements in the Requirements section.</li>
              <li>AI classifies them as Functional or Non-Functional.</li>
              <li>Guidance and examples help improve requirement quality.</li>
            </List>

            <SubTitle title="AI Test Case Generator" />
            <List>
              <li>
                Click <strong>Generate Test Cases</strong> after adding requirements.
              </li>
              <li>AI generates step-by-step test cases.</li>
              <li>Download test cases for later use.</li>
            </List>
          </HelpSection>

          {/* Metrics */}
          <HelpSection icon={BarChart3} title="Metrics & Calendar">
            <SubTitle title="Metrics Calculator" />
            <List>
              <li>Select metrics such as Defect Density or Code Coverage.</li>
              <li>Enter defect count and lines of code.</li>
              <li>Instantly view calculated results.</li>
            </List>

            <SubTitle title="Calendar View" />
            <List>
              <li>Track project deadlines visually.</li>
              <li>Switch between Month, Week, and Day views.</li>
            </List>
          </HelpSection>

          {/* Profile & Security */}
          <HelpSection icon={User} title="Profile & Security">
            <List>
              <li>Update personal details like name, country, and bio.</li>
              <li>All data is secured using Firebase Authentication and Firestore.</li>
            </List>
          </HelpSection>

          {/* FAQs */}
          <HelpSection icon={HelpCircle} title="Frequently Asked Questions">
            <FAQ
              q="Can I recover a project after deleting it?"
              a="No. Deleted projects are permanently removed from the database."
            />
            <FAQ
              q="How accurate are the AI results?"
              a="AI is highly reliable, but clear inputs always produce better results."
            />
            <FAQ
              q="Can someone edit my project using a shareable link?"
              a="No. Shareable links are strictly view-only."
            />
          </HelpSection>
        </div>
      </main>

      <Footer />
    </div>
  );
}

/* ---------------- UI Components ---------------- */

function HelpSection({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border bg-white p-8 shadow-sm">
      <h2 className="mb-6 flex items-center gap-3 text-2xl font-semibold text-gray-900">
        <Icon className="h-6 w-6 text-indigo-600" />
        {title}
      </h2>
      {children}
    </section>
  );
}

function SubTitle({ title }: { title: string }) {
  return (
    <h3 className="mt-8 mb-3 text-lg font-semibold text-gray-800">
      {title}
    </h3>
  );
}

function List({ children }: { children: React.ReactNode }) {
  return (
    <ul className="list-disc space-y-3 pl-6 text-lg text-gray-700">
      {children}
    </ul>
  );
}

function FAQ({ q, a }: { q: string; a: string }) {
  return (
    <div className="mb-6 max-w-4xl">
      <p className="text-lg font-semibold text-gray-900">Q: {q}</p>
      <p className="mt-2 text-lg text-gray-700">A: {a}</p>
    </div>
  );
}
