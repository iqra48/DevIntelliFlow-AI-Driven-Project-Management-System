"use client";

import React, { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowUp, ClipboardCheck, Edit3, FileText, Loader2, Plus, Sparkles } from "lucide-react";
import { motion, Variants } from "framer-motion";
import {
  collectFinalRequirements,
  FinalRequirement,
  generateTestCases,
  processRequirementsFile,
  processRequirementsText,
  projectRequirementsStorageKey,
  saveRequirementHistory,
  TestCaseBundle,
} from "@/lib/requirementApi";
import RequirementHistoryList from "@/components/RequirementHistoryList";
import DownloadButton from "@/components/DownloadButton";
import { doc, getDoc } from "firebase/firestore";
import { db } from "@/firebase/firebaseConfig";
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.12 } },
};

const fadeCard: Variants = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
};

function RequirementCard({
  item,
  onUpdate,
}: {
  item: FinalRequirement;
  onUpdate: (id: string, value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.requirement);

  return (
    <motion.div
      variants={fadeCard}
      className="bg-white rounded-lg p-4 border border-gray-200 shadow-sm"
    >
      {editing ? (
        <div className="space-y-3">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={3}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 outline-none focus:border-purple-600 focus:ring-2 focus:ring-purple-200"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setDraft(item.requirement);
                setEditing(false);
              }}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                onUpdate(item.id, draft);
                setEditing(false);
              }}
              className="rounded-md bg-purple-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-purple-800"
            >
              Save
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm leading-6 text-gray-800">{item.requirement}</p>
          </div>
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="rounded-md px-2 py-1 text-sm font-medium text-purple-700 hover:bg-purple-50"
          >
            Edit
          </button>
        </div>
      )}
    </motion.div>
  );
}

export default function RequirementsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [activeTab, setActiveTab] = useState<"generate" | "history">("generate");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [requirements, setRequirements] = useState<FinalRequirement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [projectName, setProjectName] = useState<string>("Project");
  const [testCasesLoading, setTestCasesLoading] = useState(false);
  const [testCasesError, setTestCasesError] = useState<string | null>(null);
  const [testCaseBundles, setTestCaseBundles] = useState<TestCaseBundle[]>([]);
  const [testCaseStatus, setTestCaseStatus] = useState<string | null>(null);
  const [testCaseWarnings, setTestCaseWarnings] = useState<string[]>([]);

  const functionalList = requirements.filter((item) => item.classification_type === "FR");
  const nonFunctionalList = requirements.filter((item) => item.classification_type === "NFR");

  useEffect(() => {
    if (!params?.id) return;

    const fetchProjectName = async () => {
      try {
        const snap = await getDoc(doc(db, "projects", params.id));
        if (snap.exists()) {
          setProjectName(snap.data().name || "Project");
        }
      } catch (err) {
        console.error("Failed to fetch project name", err);
      }
    };

    fetchProjectName();
  }, [params?.id]);

  const persistRequirements = (items: FinalRequirement[]) => {
    if (!params?.id) return;
    sessionStorage.setItem(projectRequirementsStorageKey(params.id), JSON.stringify(items));
  };

  const updateRequirement = (id: string, value: string) => {
    const updated = requirements.map((item) =>
      item.id === id ? { ...item, requirement: value.trim() } : item
    );
    setRequirements(updated);
    persistRequirements(updated);
  };

  const onFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    setUploadedFile(file);
    setError(null);
  };

  const fetchClassifiedData = async () => {
    if (!uploadedFile && !text.trim()) {
      setError("Please write requirements or upload a file first.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = uploadedFile
        ? await processRequirementsFile(uploadedFile)
        : await processRequirementsText(text.trim());
      const finalRequirements = collectFinalRequirements(data.results || []);

      setRequirements(finalRequirements);
      persistRequirements(finalRequirements);

      if (!finalRequirements.length) {
        setError("Backend processed the input but returned no final FR/NFR requirements.");
      } else if (params?.id) {
        saveRequirementHistory(
          params.id,
          finalRequirements,
          text.trim(),
          uploadedFile?.name || null
        ).catch((err) => console.error("Failed to save requirement history:", err));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Requirement generation failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateTestCases = async () => {
    if (!requirements.length) {
      setTestCasesError("Generate requirements first so test cases can be created from them.");
      return;
    }

    setTestCasesLoading(true);
    setTestCasesError(null);
    setTestCaseBundles([]);
    setTestCaseStatus(null);
    setTestCaseWarnings([]);

    try {
      const result = await generateTestCases({
        requirements: requirements.map(({ id, requirement, classification_type }) => ({
          id,
          requirement,
          classification_type,
        })),
        project_context: projectName ? `Project: ${projectName}` : null,
        output_standard: "Professional QA test case format",
      });

      setTestCaseBundles(result.bundles || []);
      setTestCaseStatus(result.status);
      setTestCaseWarnings(result.warnings || []);
    } catch (err) {
      setTestCasesError(err instanceof Error ? err.message : "Test case generation failed.");
    } finally {
      setTestCasesLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <header className="text-center">
        <h1 className="text-3xl font-extrabold bg-gradient-to-r from-purple-700 via-purple-900 to-blue-700 bg-clip-text text-transparent">
          Requirements Classification
        </h1>
        <p className="mt-2 text-sm text-gray-600">
          Write requirements or upload a document, then generate final FR/NFR requirements.
        </p>
      </header>

      {/* Tab Switcher */}
      <div className="flex justify-center gap-2">
        <button
          type="button"
          onClick={() => setActiveTab("generate")}
          className={`rounded-full px-5 py-2 text-sm font-semibold transition ${
            activeTab === "generate"
              ? "bg-purple-700 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          Generate
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("history")}
          className={`rounded-full px-5 py-2 text-sm font-semibold transition ${
            activeTab === "history"
              ? "bg-purple-700 text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          History
        </button>
      </div>

      {activeTab === "generate" && (
        <>
          <section className="space-y-4">
            <div className="flex items-center gap-2">
              <Edit3 size={18} className="text-purple-600" />
              <h2 className="text-lg font-bold text-gray-700">Requirement Input</h2>
            </div>

            <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
              <textarea
                rows={8}
                value={text}
                onChange={(event) => {
                  setText(event.target.value);
                  if (uploadedFile) setUploadedFile(null);
                }}
                placeholder="Write your project idea, user stories, or rough requirements here..."
                className="w-full resize-none rounded-t-lg border-none bg-transparent p-4 text-gray-700 outline-none"
              />

              <div className="flex flex-col gap-3 border-t border-gray-100 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-center gap-2 text-sm text-gray-600">
                  <FileText size={16} className="shrink-0 text-purple-700" />
                  <span className="truncate">
                    {uploadedFile ? uploadedFile.name : "PDF, DOCX, TXT, CSV, or XLSX supported"}
                  </span>
                </div>

                <div className="flex justify-end gap-3">
                  <input
                    type="file"
                    ref={fileInputRef}
                    accept=".pdf,.doc,.docx,.txt,.csv,.xlsx"
                    onChange={onFileSelect}
                    className="hidden"
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex h-11 w-11 items-center justify-center rounded-full border border-gray-300 bg-gray-50 text-purple-700 transition hover:bg-purple-50"
                    title="Upload file"
                  >
                    <Plus size={22} />
                  </button>
                  <button
                    type="button"
                    onClick={fetchClassifiedData}
                    disabled={loading}
                    className="flex h-11 min-w-11 items-center justify-center rounded-full bg-purple-700 px-3 text-white transition hover:bg-purple-800 disabled:cursor-not-allowed disabled:opacity-60"
                    title="Generate requirements"
                  >
                    {loading ? <Loader2 size={22} className="animate-spin" /> : <ArrowUp size={22} />}
                  </button>
                </div>
              </div>
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}
          </section>

          {requirements.length > 0 && (
            <section className="space-y-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-xl font-bold text-gray-800">Generated Requirements</h2>
                  <p className="text-sm text-gray-500">
                    {requirements.length} final requirements generated.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={handleGenerateTestCases}
                    disabled={testCasesLoading}
                    className="inline-flex items-center gap-2 rounded-lg bg-purple-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-purple-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {testCasesLoading ? <Loader2 size={17} className="animate-spin" /> : <Sparkles size={17} />}
                    Generate Test Cases
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (params?.id) {
                        router.push(`/projects/${params.id}/testcase`);
                      }
                    }}
                    className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 shadow-sm transition hover:bg-gray-50"
                  >
                    <ClipboardCheck size={17} />
                    Open Full Generator
                  </button>
                  <DownloadButton requirements={requirements} projectName={projectName} />
                </div>
              </div>

              {testCasesError && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {testCasesError}
                </div>
              )}

              {testCaseStatus && (
                <section className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                  Backend status: <span className="font-semibold">{testCaseStatus}</span>
                  {testCaseWarnings.length > 0 && (
                    <ul className="mt-2 list-disc space-y-1 pl-5">
                      {testCaseWarnings.map((warning, index) => (
                        <li key={index}>{warning}</li>
                      ))}
                    </ul>
                  )}
                </section>
              )}

              {testCaseBundles.length > 0 && (
                <section className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-lg font-bold text-gray-800">Generated Test Cases Preview</h3>
                    <span className="text-sm text-gray-500">
                      {testCaseBundles.reduce((total, bundle) => total + bundle.test_cases.length, 0)} test cases
                    </span>
                  </div>
                  <div className="space-y-3">
                    {testCaseBundles.flatMap((bundle) =>
                      bundle.test_cases.map((testCase) => (
                        <div
                          key={`${bundle.requirement_id}-${testCase.test_case_id}`}
                          className="rounded-lg border border-gray-200 bg-gray-50 p-4"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-semibold uppercase tracking-wide text-purple-700">
                              {testCase.test_case_id}
                            </span>
                            <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
                              {testCase.test_type}
                            </span>
                            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
                              {testCase.priority}
                            </span>
                          </div>
                          <h4 className="mt-2 font-semibold text-gray-900">{testCase.title}</h4>
                          <p className="mt-1 text-sm text-gray-600">{testCase.objective}</p>
                        </div>
                      ))
                    )}
                  </div>
                </section>
              )}

              <div className="grid gap-6 xl:grid-cols-2">
                <motion.div variants={containerVariants} initial="hidden" animate="show">
                  <h3 className="mb-3 text-lg font-bold text-gray-800">
                    Functional Requirements ({functionalList.length})
                  </h3>
                  <div className="space-y-3">
                    {functionalList.length ? (
                      functionalList.map((item) => (
                        <RequirementCard key={item.id} item={item} onUpdate={updateRequirement} />
                      ))
                    ) : (
                      <p className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-500">
                        No functional requirements returned.
                      </p>
                    )}
                  </div>
                </motion.div>

                <motion.div variants={containerVariants} initial="hidden" animate="show">
                  <h3 className="mb-3 text-lg font-bold text-gray-800">
                    Non-Functional Requirements ({nonFunctionalList.length})
                  </h3>
                  <div className="space-y-3">
                    {nonFunctionalList.length ? (
                      nonFunctionalList.map((item) => (
                        <RequirementCard key={item.id} item={item} onUpdate={updateRequirement} />
                      ))
                    ) : (
                      <p className="rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-500">
                        No non-functional requirements returned.
                      </p>
                    )}
                  </div>
                </motion.div>
              </div>
            </section>
          )}
        </>
      )}

      {activeTab === "history" && params?.id && (
        <section className="space-y-4">
          <h2 className="text-lg font-bold text-gray-700">Requirement Generation History</h2>
          <RequirementHistoryList projectId={params.id} projectName={projectName} />
        </section>
      )}
    </div>
  );
}