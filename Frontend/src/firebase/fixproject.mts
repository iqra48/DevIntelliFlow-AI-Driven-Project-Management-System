import { db } from "./firebaseConfig"; 
import { collection, getDocs, doc, updateDoc } from "firebase/firestore";

async function fixProjects() {
  const projectsRef = collection(db, "projects");
  const snapshot = await getDocs(projectsRef);

  for (const projectDoc of snapshot.docs) {
    const data = projectDoc.data();
    const collaborators = Array.isArray(data.collaborators) ? data.collaborators : [];
    const collaboratorUids = Array.isArray(data.collaboratorUids) ? data.collaboratorUids : [];

    const newUids: string[] = [...collaboratorUids];

    for (const c of collaborators) {
      if (c.uid && !newUids.includes(c.uid)) {
        newUids.push(c.uid);
      }
    }

    await updateDoc(doc(db, "projects", projectDoc.id), {
      collaborators,
      collaboratorUids: newUids,
    });

    console.log(`Fixed project: ${projectDoc.id}`);
  }

  console.log("All projects fixed!");
}

fixProjects().catch(console.error);
