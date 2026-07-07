"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { FileDown, Loader2, Sparkles } from "lucide-react";
import { motion, Variants } from "framer-motion";
import {
  collectFinalRequirements,
  FinalRequirement,
  generateTestCases,
  GeneratedTestCase,
  processRequirementsText,
  projectRequirementsStorageKey,
  TestCaseBundle,
} from "@/lib/requirementApi";

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.12 } },
};

const cardVariants: Variants = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
};

function TestCaseCard({
  testCase,
  requirementText,
}: {
  testCase: GeneratedTestCase;
  requirementText: string;
}) {
  return (
    <motion.div
      variants={cardVariants}
      className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
    >
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-purple-700">
            {testCase.test_case_id}
          </p>
          <h4 className="mt-1 text-lg font-semibold text-gray-900">{testCase.title}</h4>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <span className="rounded-full bg-blue-50 px-2.5 py-1 text-blue-700">
            {testCase.test_type}
          </span>
          <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
            {testCase.priority}
          </span>
        </div>
      </div>

      <div className="space-y-4 text-sm text-gray-700">
        <div>
          <p className="font-semibold text-gray-900">Requirement Covered</p>
          <p className="mt-1 leading-6">{requirementText}</p>
        </div>

        {testCase.objective && (
          <div>
            <p className="font-semibold text-gray-900">Objective</p>
            <p className="mt-1 leading-6">{testCase.objective}</p>
          </div>
        )}

        {testCase.preconditions?.length > 0 && (
          <div>
            <p className="font-semibold text-gray-900">Preconditions</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {testCase.preconditions.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <p className="font-semibold text-blue-700">Steps</p>
          <ol className="mt-1 list-decimal space-y-2 pl-5">
            {testCase.steps.map((step) => (
              <li key={step.step_number}>
                <span>{step.action}</span>
                <span className="block text-gray-500">{step.expected_result}</span>
              </li>
            ))}
          </ol>
        </div>

        <div>
          <p className="font-semibold text-gray-900">Expected Result</p>
          <p className="mt-1 leading-6">{testCase.expected_result}</p>
        </div>

        {testCase.assumptions?.length > 0 && (
          <div>
            <p className="font-semibold text-gray-900">Assumptions</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {testCase.assumptions.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </motion.div>
  );
}

export default function TestCasePage() {
  const params = useParams<{ id: string }>();
  const [requirementInput, setRequirementInput] = useState("");
  const [projectContext, setProjectContext] = useState("");
  const [bundles, setBundles] = useState<TestCaseBundle[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params?.id) return;

    try {
      const raw = sessionStorage.getItem(projectRequirementsStorageKey(params.id));
      if (!raw) return;

      const parsed = JSON.parse(raw) as FinalRequirement[];
      const formatted = parsed
        .map((item) => `${item.classification_type}: ${item.requirement}`)
        .filter(Boolean)
        .join("\n\n");

      if (formatted.trim()) {
        setRequirementInput(formatted);
      }
    } catch {
      // Ignore invalid persisted data.
    }
  }, [params?.id]);

  const runGeneration = async () => {
    if (!requirementInput.trim()) {
      setError("Paste a requirement, user story, or feature description first.");
      return;
    }

    setLoading(true);
    setError(null);
    setBundles([]);
    setStatus(null);
    setWarnings([]);

    try {
      const processed = await processRequirementsText(requirementInput.trim());
      const finalRequirements = collectFinalRequirements(processed.results || []).slice(0, 5);

      if (!finalRequirements.length) {
        setError("No final FR/NFR requirements were generated from this input.");
        return;
      }

      const result = await generateTestCases({
        requirements: finalRequirements.map(({ id, requirement, classification_type }) => ({
          id,
          requirement,
          classification_type,
        })),
        project_context: projectContext.trim() || null,
        output_standard: "Professional QA test case format",
      });

      setBundles(result.bundles || []);
      setStatus(result.status);
      setWarnings(result.warnings || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test case generation failed.");
    } finally {
      setLoading(false);
    }
  };

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify({ status, bundles, warnings }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "test_cases.json";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-8">
      <header className="text-center">
        <h1 className="text-3xl font-extrabold bg-gradient-to-r from-purple-700 via-purple-900 to-blue-700 bg-clip-text text-transparent">
          Test Case Generator
        </h1>
        <p className="mt-2 text-sm text-gray-600">
          Paste a requirement or feature description, add optional context, and generate QA test cases.
        </p>
      </header>

      <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
          <Sparkles className="text-purple-600" size={20} />
          Generate Test Cases
        </h2>

        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <label className="mb-2 block text-sm font-semibold text-gray-700">
              Requirement or feature input
            </label>
            <textarea
              value={requirementInput}
              onChange={(event) => setRequirementInput(event.target.value)}
              placeholder="Paste a requirement, user story, or feature description..."
              className="h-40 w-full resize-none rounded-lg border border-gray-300 bg-gray-50 p-3 text-sm text-gray-700 outline-none focus:border-purple-600 focus:ring-2 focus:ring-purple-200"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-semibold text-gray-700">
              Project context <span className="font-normal text-gray-500">(optional)</span>
            </label>
            <textarea
              value={projectContext}
              onChange={(event) => setProjectContext(event.target.value)}
              placeholder="Optional: add system domain, user roles, business rules, platform, or constraints for better test cases..."
              className="h-40 w-full resize-none rounded-lg border border-gray-300 bg-gray-50 p-3 text-sm text-gray-700 outline-none focus:border-purple-600 focus:ring-2 focus:ring-purple-200"
            />
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-5 flex justify-end">
          <button
            type="button"
            onClick={runGeneration}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-lg bg-purple-700 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-purple-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
            {loading ? "Generating..." : "Generate Test Cases"}
          </button>
        </div>
      </section>

      {status && (
        <section className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          Backend status: <span className="font-semibold">{status}</span>
          {warnings.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {warnings.map((warning, index) => (
                <li key={index}>{warning}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {bundles.length > 0 && (
        <section className="space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-xl font-bold text-gray-800">Generated Test Cases</h3>
              <p className="text-sm text-gray-500">
                {bundles.reduce((total, bundle) => total + bundle.test_cases.length, 0)} test
                cases generated.
              </p>
            </div>
            <button
              type="button"
              onClick={downloadJson}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800"
            >
              <FileDown size={17} />
              Download JSON
            </button>
          </div>

          <motion.div
            className="space-y-5"
            variants={containerVariants}
            initial="hidden"
            animate="show"
          >
            {bundles.flatMap((bundle) =>
              bundle.test_cases.map((testCase) => (
                <TestCaseCard
                  key={`${bundle.requirement_id}-${testCase.test_case_id}`}
                  testCase={testCase}
                  requirementText={bundle.requirement_text}
                />
              ))
            )}
          </motion.div>
        </section>
      )}
    </div>
  );
}
