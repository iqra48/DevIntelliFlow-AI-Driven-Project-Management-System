import {
  collection,
  addDoc,
  getDocs,
  orderBy,
  query,
  serverTimestamp,
  Timestamp,
} from "firebase/firestore";
import { db } from "@/firebase/firebaseConfig";


export const REQUIREMENT_API_BASE =
  process.env.NEXT_PUBLIC_REQUIREMENT_API_BASE?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type RequirementType = "FR" | "NFR";

export interface BackendRequirement {
  id?: string;
  requirement?: string;
  rewritten?: string;
  original_generated?: string;
  original_requirement?: string;
  classification_type?: string;
  requirement_type?: string;
  classification?: {
    type?: string;
    label?: string;
    confidence?: number;
    status?: string;
  };
}

export interface FinalRequirement {
  id: string;
  requirement: string;
  classification_type: RequirementType;
  confidenceScore: number | null;
}

export interface RequirementProcessResponse {
  status?: string;
  results?: BackendRequirement[];
}

export interface TestCaseStep {
  step_number: number;
  action: string;
  expected_result: string;
}

export interface TestScenario {
  scenario: string;
  expected_result?: string | null;
}

export interface GeneratedTestCase {
  test_case_id: string;
  requirement_id: string;
  title: string;
  objective: string;
  test_type: string;
  priority: string;
  preconditions: string[];
  test_data: Record<string, unknown>;
  steps: TestCaseStep[];
  expected_result: string;
  negative_scenarios: TestScenario[];
  edge_cases: TestScenario[];
  assumption_required: boolean;
  assumptions: string[];
}

export interface TestCaseBundle {
  requirement_id: string;
  requirement_text: string;
  requirement_type: RequirementType;
  test_cases: GeneratedTestCase[];
}

export interface TestCaseGenerationResponse {
  status: string;
  bundles: TestCaseBundle[];
  total_requirements: number;
  total_test_cases: number;
  warnings?: string[] | null;
}

async function parseApiError(response: Response, fallback: string) {
  try {
    const data = await response.json();
    if (typeof data?.detail === "string") return data.detail;
    if (data?.detail) return JSON.stringify(data.detail);
  } catch {
    const text = await response.text().catch(() => "");
    if (text) return text;
  }

  return fallback;
}

export async function processRequirementsText(text: string) {
  const response = await fetch(`${REQUIREMENT_API_BASE}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response, "Failed to process requirements."));
  }

  return (await response.json()) as RequirementProcessResponse;
}

export async function processRequirementsFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${REQUIREMENT_API_BASE}/process_file`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response, "Failed to process uploaded file."));
  }

  return (await response.json()) as RequirementProcessResponse;
}

export async function generateTestCases(payload: {
  requirements: Pick<FinalRequirement, "id" | "requirement" | "classification_type">[];
  project_context?: string | null;
  output_standard?: string | null;
}) {
  const response = await fetch(`${REQUIREMENT_API_BASE}/generate_test_cases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await parseApiError(response, "Failed to generate test cases."));
  }

  const data = await response.json();
  
  // Transform backend response to match frontend expectation
  const bundles = (data.results || []).map((result: any) => ({
    requirement_id: result.requirement_id,
    requirement_text: result.requirement_text,
    requirement_type: result.requirement_type,
    test_cases: result.test_cases || [],
  }));
  
  const total_test_cases = bundles.reduce((sum: number, bundle: TestCaseBundle) => sum + (bundle.test_cases?.length || 0), 0);
  
  return {
    status: data.status,
    bundles,
    total_requirements: bundles.length,
    total_test_cases,
    warnings: data.warnings,
  } as TestCaseGenerationResponse;
}

export function collectFinalRequirements(results: BackendRequirement[] = []) {
  return results.reduce<FinalRequirement[]>((acc, item, index) => {
    const rawLabel =
      item.classification_type ||
      item.classification?.type ||
      item.classification?.label ||
      item.requirement_type ||
      "";
    const label = rawLabel.trim().toUpperCase();

    if (label !== "FR" && label !== "NFR") return acc;

    const requirement = (
      item.requirement ||
      item.rewritten ||
      item.original_generated ||
      item.original_requirement ||
      ""
    ).trim();

    if (!requirement) return acc;

    const confidence = item.classification?.confidence;
    const confidenceScore =
      typeof confidence === "number"
        ? Math.round((confidence <= 1 ? confidence * 100 : confidence) * 100) / 100
        : null;

    acc.push({
      id: item.id || `REQ_${index + 1}`,
      requirement,
      classification_type: label,
      confidenceScore,
    });

    return acc;
  }, []);
}

export function projectRequirementsStorageKey(projectId: string) {
  return `devintelliflow:requirements:${projectId}`;
}

/* ----------------------------------------------------------------
   Requirement Generation History (Firestore)
   ---------------------------------------------------------------- */

export interface RequirementHistoryEntry {
  id: string;
  generatedAt: Timestamp;
  inputText: string | null;
  fileName: string | null;
  requirements: FinalRequirement[];
}

export async function saveRequirementHistory(
  projectId: string,
  requirements: FinalRequirement[],
  inputText: string,
  fileName: string | null
) {
  const ref = collection(db, "projects", projectId, "requirementHistory");
  await addDoc(ref, {
    generatedAt: serverTimestamp(),
    inputText: inputText || null,
    fileName: fileName || null,
    requirements,
  });
}

export async function getRequirementHistory(
  projectId: string
): Promise<RequirementHistoryEntry[]> {
  const ref = collection(db, "projects", projectId, "requirementHistory");
  const q = query(ref, orderBy("generatedAt", "desc"));
  const snapshot = await getDocs(q);

  return snapshot.docs.map((doc) => ({
    id: doc.id,
    ...(doc.data() as Omit<RequirementHistoryEntry, "id">),
  }));
}