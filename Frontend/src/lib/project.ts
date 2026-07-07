import { db } from "@/firebase/firebaseConfig";
import {
  collection,
  addDoc,
  getDocs,
  query,
  where,
  updateDoc,
  deleteDoc,
  doc,
  serverTimestamp,
} from "firebase/firestore";


export interface ProjectData {
  id?: string;
  name: string;
  description?: string;
  priority?: "Low" | "Medium" | "High" | "Urgent";
  status: "Not Started" | "In Progress" | "Completed" | "On Hold";
  ownerId: string;
  ownerEmail: string;
  createdAt: any;
  lastOpenedAt?: any;
  startDate?: string;
  dueDate?: string;
  timeEstimate?: number | null; // days between start & due   
  shareLinkEnabled?: boolean;

}

// Create project
export async function createProject(
  ownerId: string,
  ownerEmail: string,
  data: Omit<
    ProjectData,
    "id" | "ownerId" | "ownerEmail" | "createdAt" | "lastOpenedAt"
  >
) {
  const projectsRef = collection(db, "projects");

  const projectDoc = await addDoc(projectsRef, {
    ...data,
    ownerId,
    ownerEmail,
    createdAt: serverTimestamp(),
    lastOpenedAt: serverTimestamp(),
  });

  return projectDoc.id;
}


// Fetch user projects
export async function fetchUserProjects(
  ownerId: string
): Promise<ProjectData[]> {
  const projectsRef = collection(db, "projects");
  const q = query(projectsRef, where("ownerId", "==", ownerId));
  const snapshot = await getDocs(q);

  return snapshot.docs.map((docSnap) => ({
    id: docSnap.id,
    ...(docSnap.data() as ProjectData),
  }));
}

// ✅ Update project
export async function updateProject(
  projectId: string,
  updates: Partial<ProjectData>
) {
  const projectRef = doc(db, "projects", projectId);
  await updateDoc(projectRef, updates);
}

// ✅ Delete project
export async function deleteProject(projectId: string) {
  const projectRef = doc(db, "projects", projectId);
  await deleteDoc(projectRef);
}

// ✅ Mark project opened
export async function markProjectOpened(projectId: string) {
  const projectRef = doc(db, "projects", projectId);
  await updateDoc(projectRef, { lastOpenedAt: serverTimestamp() });
}
