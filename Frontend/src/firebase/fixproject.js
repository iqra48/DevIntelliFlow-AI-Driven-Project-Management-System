// src/firebase/fixproject.js
import { db } from "./firebaseConfig.js";
import { collection, getDocs, doc, updateDoc } from "firebase/firestore";

async function fixProjects() {
  const projectsRef = collection(db, "projects");
  const snapshot = await getDocs(projectsRef);

  for (const projectDoc of snapshot.docs) {
    const data = projectDoc.data();
    const collaborators = data.collaborators || {};
    const collaboratorUids = Array.isArray(data.collaboratorUids)
      ? data.collaboratorUids
      : [];

    const newUids = [...collaboratorUids];

    for (const uid of Object.keys(collaborators)) {
      if (!newUids.includes(uid)) newUids.push(uid);
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
