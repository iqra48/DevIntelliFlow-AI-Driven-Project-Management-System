// "use client";

// import { useEffect, useState } from "react";
// import Navbar from "@/components/Navbar";
// import Sidebar from "@/components/Sidebar";
// import ProjectCreationModal from "@/components/ProjectCreationModal";
// import ProjectCard from "@/components/ProjectCard";
// import SearchBar from "@/components/SearchBar";
// import { db } from "@/firebase/firebaseConfig";
// import { FolderOpen, FolderPlus } from "lucide-react";
// import { collection, onSnapshot, orderBy, query, where } from "firebase/firestore";
// import { Project } from "@/types/project";
// import Link from "next/link";
// import { useAuth } from "@/context/AuthContext";

// export default function ProjectsPage() {
//   const { user, loading: checkingAuth } = useAuth();
//   const [openModal, setOpenModal] = useState(false);
//   const [projects, setProjects] = useState<Project[]>([]);
//   const [filtered, setFiltered] = useState<Project[]>([]);
//   const [loadingData, setLoadingData] = useState(true);
//   const [searchQuery, setSearchQuery] = useState("");

//   useEffect(() => {
//     if (!user) {
//       setProjects([]);
//       setFiltered([]);
//       setLoadingData(false);
//       return;
//     }

//     setLoadingData(true);

//     const qOwner = query(
//       collection(db, "projects"),
//       where("ownerId", "==", user.uid),
//       orderBy("createdAt", "desc")
//     );

//     const unsubOwner = onSnapshot(
//       qOwner,
//       (snap) => {
//         const ownerProjects: Project[] = snap.docs.map((doc) => {
//           const data = doc.data() as Omit<Project, "id">;
//           return { ...data, id: doc.id };
//         });

//         setProjects(ownerProjects);
//         setFiltered(ownerProjects);
//         setLoadingData(false);
//       },
//       (error) => {
//         console.error("Projects snapshot error:", error);
//         if (error.code === "permission-denied") {
//           setProjects([]);
//           setFiltered([]);
//         }
//         setLoadingData(false);
//       }
//     );

//     return () => unsubOwner();
//   }, [user]);

//   const onSearch = (res: Project[], query: string) => {
//     setFiltered(res);
//     setSearchQuery(query);
//   };

//   const priorityLevels = ["Urgent", "High", "Medium", "Low"];
//   const headerColors: Record<string, string> = {
//     Urgent: "bg-[#FF5A5F]",
//     High: "bg-[#FF9500]",
//     Medium: "bg-[#FFC107]",
//     Low: "bg-[#A8A29E]",
//   };

//   const grouped: Record<string, Project[]> = {
//     Urgent: [],
//     High: [],
//     Medium: [],
//     Low: [],
//   };
//   filtered.forEach((p) => {
//     if (grouped[p.priority as keyof typeof grouped]) {
//       grouped[p.priority as keyof typeof grouped].push(p);
//     }
//   });

//   if (checkingAuth) {
//     return (
//       <section className="flex h-screen items-center justify-center">
//         <span className="text-gray-600 text-lg animate-pulse">
//           Checking your account...
//         </span>
//       </section>
//     );
//   }

//   if (!user) {
//     return (
//       <section className="flex h-screen items-center justify-center">
//         <div className="rounded-xl bg-gray-100 p-6 shadow-md text-center max-w-sm">
//           <h2 className="text-gray-700 font-medium">
//             You need to sign in to access your workspace.
//           </h2>
//         </div>
//       </section>
//     );
//   }

//   return (
//     <div className="flex flex-col h-screen bg-[#F8F9FB]/90">
//       <Navbar />
//       <div className="flex flex-1">
//         <Sidebar />

//         <main
//           className={`flex-1 px-3 sm:px-4 pt-16 pb-8 transition-all duration-300 ${
//             openModal ? "blur-sm" : ""
//           } ml-12 sm:ml-16 lg:ml-64`}
//         >
//           {/* Page Header */}
//           <header className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
//             <div>
//               <h1 className="text-3xl font-bold text-gray-700 tracking-tight">
//                 Projects
//               </h1>
//               <p className="mt-2 text-gray-400">
//                 Manage your projects by priority
//               </p>
//             </div>

//             {projects.length > 0 && (
//               <button
//                 onClick={() => setOpenModal(true)}
//                 className="flex items-center justify-center rounded-lg bg-gradient-to-r from-purple-700 to-purple-600 hover:from-purple-600 hover:to-purple-500 shadow-md px-4 py-2 text-sm font-semibold text-white transition-transform transform hover:scale-105 active:scale-95"
//               >
//                 <FolderPlus className="w-5 h-5 mr-2" />
//                 Add Project
//               </button>
//             )}
//           </header>

//           {/* Search Bar */}
//           {projects.length > 0 && (
//             <div className="mb-6">
//               <SearchBar
//                 projects={projects}
//                 onSearch={onSearch}
//               />
//             </div>
//           )}

//           {/* Main Content */}
//           {loadingData ? (
//             <div className="mt-12 text-center text-gray-500 animate-pulse">
//               Loading your projects...
//             </div>
//           ) : filtered.length > 0 ? (
//             <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
//               {priorityLevels.map((priority) => (
//                 <div
//                   key={priority}
//                   className="flex flex-col bg-gray-50 shadow-md border overflow-hidden"
//                 >
//                   <div className={`h-1.5 w-full ${headerColors[priority]}`} />
//                   <div className="p-3 border-b bg-gray-50/70">
//                     <h2 className="text-base font-bold text-gray-700 flex items-center justify-between">
//                       {priority}
//                       <span className="ml-2 text-xs text-gray-500">
//                         {grouped[priority].length}
//                       </span>
//                     </h2>
//                   </div>
//                   <div className="flex-1 p-4 space-y-4 overflow-y-auto">
//                     {grouped[priority].length > 0 ? (
//                       grouped[priority].map((proj) => (
//                         <Link key={proj.id} href={`/projects/${proj.id}`} className="block">
//                           <ProjectCard project={proj} />
//                         </Link>
//                       ))
//                     ) : (
//                       <p className="text-sm text-gray-400 italic">
//                         No {priority.toLowerCase()} priority projects
//                       </p>
//                     )}
//                   </div>
//                 </div>
//               ))}
//             </div>
//           ) : searchQuery.trim() !== "" ? (
//            <div className="mt-24 flex flex-col items-center justify-center text-center">
//            <img
//              src="/search_no_result.png"
//              alt="No search results"
//              className="w-74 h-auto mb-6 opacity-90"
//            />
         
//            <h2 className="text-2xl font-bold text-gray-800 mb-2">
//              No Projects Found
//            </h2>
         
//            <p className="text-sm text-gray-500 max-w-sm">
//              Try adjusting your search keywords or check for spelling mistakes.
//            </p>
//           </div>
//           ) : (
//             // "No Projects Yet" section
//             <div className="mt-20 flex justify-center">
//               <div className="max-w-md w-full rounded-xl bg-gradient-to-br from-gray-100 to-stone-100 px-8 py-10 text-center shadow-xl border-2 border-purple-300 border-dashed">
//                 <div className="flex justify-center mb-4">
//                   <div className="w-14 h-14 flex items-center justify-center rounded-full bg-purple-100 text-purple-700">
//                     <FolderOpen className="w-7 h-7" />
//                   </div>
//                 </div>
//                 <h2 className="mb-2 text-2xl font-bold text-gray-800">
//                   No Projects Yet
//                 </h2>
//                 <p className="mb-6 text-gray-500 text-sm">
//                   Start building your journey by creating your very first project.
//                 </p>
//                 <button
//                   onClick={() => setOpenModal(true)}
//                   className="rounded-lg bg-gradient-to-r from-purple-800 to-purple-700 hover:from-purple-600 hover:to-purple-500 text-white px-6 py-3 font-medium shadow-md transition transform"
//                 >
//                   + Add Project
//                 </button>
//               </div>
//             </div>
//           )}
//         </main>
//       </div>

//       {openModal && <ProjectCreationModal onClose={() => setOpenModal(false)} />}
//     </div>
//   );
// }
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FolderOpen, FolderPlus, GripVertical } from "lucide-react";
import {
  collection,
  onSnapshot,
  orderBy,
  query,
  where,
  doc,
  updateDoc,
} from "firebase/firestore";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  useDroppable,
  useDraggable,
} from "@dnd-kit/core";

import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";
import ProjectCreationModal from "@/components/ProjectCreationModal";
import ProjectCard from "@/components/ProjectCard";
import SearchBar from "@/components/SearchBar";
import { db } from "@/firebase/firebaseConfig";
import { Project } from "@/types/project";
import { useAuth } from "@/context/AuthContext";

export default function ProjectsPage() {
  const { user, loading: checkingAuth } = useAuth();

  const [openModal, setOpenModal] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [filtered, setFiltered] = useState<Project[]>([]);
  const [loadingData, setLoadingData] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeDrag, setActiveDrag] = useState<Project | null>(null);

  /* ================= FIRESTORE ================= */
  useEffect(() => {
    if (!user) {
      setProjects([]);
      setFiltered([]);
      setLoadingData(false);
      return;
    }

    setLoadingData(true);

    const q = query(
      collection(db, "projects"),
      where("ownerId", "==", user.uid),
      orderBy("createdAt", "desc")
    );

    const unsub = onSnapshot(q, (snap) => {
      const list: Project[] = snap.docs.map((d) => ({
        ...(d.data() as Omit<Project, "id">),
        id: d.id,
      }));

      setProjects(list);
      setFiltered(list);
      setLoadingData(false);
    });

    return () => unsub();
  }, [user]);

  /* ================= SEARCH ================= */
  const onSearch = (res: Project[], query: string) => {
    setFiltered(res);
    setSearchQuery(query);
  };

  /* ================= DRAG & DROP ================= */
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;

    setActiveDrag(null);
    if (!over) return;

    const projectId = active.id as string;
    const newPriority = over.id as string;

    const project = projects.find((p) => p.id === projectId);
    if (!project || project.priority === newPriority) return;

    await updateDoc(doc(db, "projects", projectId), {
      priority: newPriority,
    });
  };

  /* ================= PRIORITIES ================= */
  const priorityLevels = ["Urgent", "High", "Medium", "Low"];

  const headerColors: Record<string, string> = {
    Urgent: "bg-[#FF5A5F]",
    High: "bg-[#FF9500]",
    Medium: "bg-[#FFC107]",
    Low: "bg-[#A8A29E]",
  };

  const grouped: Record<string, Project[]> = {
    Urgent: [],
    High: [],
    Medium: [],
    Low: [],
  };

  filtered.forEach((p) => grouped[p.priority]?.push(p));

  /* ================= DROPPABLE COLUMN ================= */
  const DroppableColumn = ({
    priority,
    children,
  }: {
    priority: string;
    children: React.ReactNode;
  }) => {
    const { setNodeRef, isOver } = useDroppable({ id: priority });

    return (
      <div
        ref={setNodeRef}
        className={`flex flex-col border bg-gray-50 shadow transition ${
          isOver ? "ring-2 ring-purple-400" : ""
        }`}
      >
        {children}
      </div>
    );
  };

  /* ================= DRAGGABLE PROJECT ================= */
  const DraggableProject = ({ project }: { project: Project }) => {
    const { setNodeRef, attributes, listeners, transform, isDragging } =
      useDraggable({
        id: project.id,
      });

    const style = {
      transform: transform
        ? `translate(${transform.x}px, ${transform.y}px)`
        : undefined,
      zIndex: isDragging ? 9999 : undefined,
    };

    return (
      <div ref={setNodeRef} style={style} className="relative">

        {/* DRAG HANDLE */}
        <div
          {...attributes}
          {...listeners}
          className="absolute top-2 right-2 cursor-grab text-gray-400 hover:text-gray-600 z-10"
          title="Drag project"
        >
          <GripVertical size={16} />
        </div>

        {/* CLICKABLE CARD */}
        <Link href={`/projects/${project.id}`} className="block">
          <ProjectCard project={project} />
        </Link>
      </div>
    );
  };

  /* ================= UI STATES ================= */
  if (checkingAuth) {
    return (
      <div className="flex h-screen items-center justify-center text-gray-500">
        Checking your account...
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="bg-gray-100 p-6 rounded-xl shadow">
          Please sign in to access projects.
        </div>
      </div>
    );
  }

  /* ================= RENDER ================= */
  return (
    <div className="flex flex-col h-screen bg-[#F8F9FB]">
      <Navbar />

      <div className="flex flex-1">
        <Sidebar />

        <main className="flex-1 px-4 pt-16 ml-12 sm:ml-16 lg:ml-64">
          <header className="mb-6 flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold text-gray-700">Projects</h1>
              <p className="text-gray-400 mt-1">Manage projects efficiently, from start to finish</p>
            </div>

            {projects.length > 0 && (
              <button
                onClick={() => setOpenModal(true)}
                className="bg-purple-600 text-white px-4 py-2 rounded-lg flex items-center gap-2"
              >
                <FolderPlus size={18} />
                Add Project
              </button>
            )}
          </header>

          {projects.length > 0 && (
            <SearchBar projects={projects} onSearch={onSearch} />
          )}

          {loadingData ? (
            <p className="mt-10 text-center text-gray-500">
              Loading projects...
            </p>
          ) : filtered.length > 0 ? (
            <DndContext
              onDragStart={(e) => {
                const dragged = projects.find(
                  (p) => p.id === e.active.id
                );
                setActiveDrag(dragged || null);
              }}
              onDragEnd={handleDragEnd}
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-6">
                {priorityLevels.map((priority) => (
                  <DroppableColumn key={priority} priority={priority}>
                    <div className={`h-1.5 ${headerColors[priority]}`} />
                    <div className="p-3 font-bold text-gray-700">
                      {priority} ({grouped[priority].length})
                    </div>
                    <div className="p-3 space-y-4 overflow-y-auto flex-1">
                      {grouped[priority].map((proj) => (
                        <DraggableProject key={proj.id} project={proj} />
                      ))}
                    </div>
                  </DroppableColumn>
                ))}
              </div>

              <DragOverlay>
                {activeDrag ? (
                  <ProjectCard project={activeDrag} />
                ) : null}
              </DragOverlay>
            </DndContext>
          ) : searchQuery ? (
            <div className="mt-24 text-center">
              <img
                src="/search_no_result.png"
                className="mx-auto mb-6 w-72"
                alt="No results"
              />
              <h2 className="text-2xl font-bold text-gray-700">
                No Projects Found
              </h2>
            </div>
          ) : (
            //"No Projects Yet" section
            <div className="mt-20 flex justify-center">
              <div className="max-w-md w-full rounded-xl bg-gradient-to-br from-gray-100 to-stone-100 px-8 py-10 text-center shadow-xl border-2 border-purple-300 border-dashed">
                <div className="flex justify-center mb-4">
                  <div className="w-14 h-14 flex items-center justify-center rounded-full bg-purple-100 text-purple-700">
                    <FolderOpen className="w-7 h-7" />
                  </div>
                </div>
                <h2 className="mb-2 text-2xl font-bold text-gray-800">
                  No Projects Yet
                </h2>
                <p className="mb-6 text-gray-500 text-sm">
                  Start building your journey by creating your very first project.
                </p>
                <button
                  onClick={() => setOpenModal(true)}
                  className="rounded-lg bg-gradient-to-r from-purple-800 to-purple-700 hover:from-purple-600 hover:to-purple-500 text-white px-6 py-3 font-medium shadow-md transition transform"
                >
                  + Add Project
                </button>
              </div>
            </div>
          )}
        </main>
      </div>

      {openModal && <ProjectCreationModal onClose={() => setOpenModal(false)} />}
    </div>
  );
}
