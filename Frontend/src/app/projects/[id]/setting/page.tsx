"use client";

import { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { doc, getDoc, updateDoc, deleteDoc } from "firebase/firestore";
import { db } from "@/firebase/firebaseConfig";
import toast from "react-hot-toast";
import { useAuth } from "@/context/AuthContext";

interface ProjectSettingsPageProps {
  params: Promise<{ id: string }>;
}

export default function ProjectSettingsPage({ params }: ProjectSettingsPageProps) {
  const router = useRouter();
  const { user } = useAuth();

  // unwrap params promise using React.use()
  const { id: projectId } = use(params);

  const [project, setProject] = useState<any>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [linkSharing, setLinkSharing] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [isOwner, setIsOwner] = useState(false);
  const [isReadOnly, setIsReadOnly] = useState(false); // shared link viewer

  useEffect(() => {
    if (!projectId) return;

    const loadProject = async () => {
      try {
        const snap = await getDoc(doc(db, "projects", projectId));
        if (!snap.exists()) {
          toast.error("Project not found");
          router.push("/projects");
          return;
        }

        const data = snap.data();
        setProject(data);
        setName(data.name || "");
        setDescription(data.description || "");
        setLinkSharing(data.shareLinkEnabled || false);

        const owner = data.ownerId;
        if (user && user.uid === owner) {
          setIsOwner(true);
        } else if (!user && data.shareLinkEnabled) {
          setIsReadOnly(true); // anyone with link
        } else {
          toast.error("You are not authorized to view this project");
          router.push("/projects");
        }
      } catch (err) {
        console.error(err);
        toast.error("Failed to load project");
        router.push("/projects");
      }
    };

    loadProject();

    if (typeof window !== "undefined") {
      setBaseUrl(window.location.origin);
    }
  }, [projectId, user]);

  const saveProjectInfo = async () => {
    if (!isOwner) return;
    try {
      await updateDoc(doc(db, "projects", projectId), { name, description });
      toast.success("Project info updated!");
    } catch (err) {
      console.error(err);
      toast.error("Failed to update project info");
    }
  };

  const updateLinkSharing = async (enabled: boolean) => {
    if (!isOwner) return;
    try {
      await updateDoc(doc(db, "projects", projectId), { shareLinkEnabled: enabled });
      setLinkSharing(enabled);
      toast.success("Link sharing updated");
    } catch (err) {
      console.error(err);
      toast.error("Failed to update link sharing");
    }
  };

  const deleteProject = async () => {
    if (!isOwner) return;
    try {
      await deleteDoc(doc(db, "projects", projectId));
      toast.success("Project deleted!");
      router.push("/projects");
    } catch (err) {
      console.error(err);
      toast.error("Failed to delete project");
    }
  };

  if (!project) return <p>Loading...</p>;

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Project Settings</h1>

      {/* Project Info */}
      <section className="mb-8 bg-white p-4 rounded-lg shadow">
        <h2 className="text-xl font-semibold mb-4">Project Info</h2>
        <label className="block mb-2">Project Name</label>
        <input
          className={`w-full border rounded p-2 mb-4 ${isReadOnly ? "bg-gray-100" : ""}`}
          value={name}
          onChange={(e) => setName(e.target.value)}
          readOnly={isReadOnly}
        />
        <label className="block mb-2">Description</label>
        <textarea
          className={`w-full border rounded p-2 mb-4 ${isReadOnly ? "bg-gray-100" : ""}`}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          readOnly={isReadOnly}
        />
        {isOwner && (
          <button
            onClick={saveProjectInfo}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Save Changes
          </button>
        )}
      </section>

      {/* Share Project */}
      {isOwner && (
        <section className="mb-8 bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4">Share Project</h2>
          <div className="flex items-center gap-2 mb-4">
            <input
              type="checkbox"
              checked={linkSharing}
              onChange={(e) => updateLinkSharing(e.target.checked)}
            />
            <span>Enable link sharing</span>
          </div>
          {linkSharing && (
            <div className="flex gap-2">
              <input
                className="flex-1 border rounded p-2"
                readOnly
                value={`${baseUrl}/projects/${projectId}`}
              />
              <button
                onClick={() => navigator.clipboard.writeText(`${baseUrl}/projects/${projectId}`)}
                className="bg-blue-600 text-white px-4 rounded hover:bg-blue-700"
              >
                Copy Link
              </button>
            </div>
          )}
        </section>
      )}

      {/* Danger Zone */}
      {isOwner && (
        <section className="bg-white p-4 rounded-lg shadow">
          <h2 className="text-xl font-semibold mb-4 text-red-600">Danger Zone</h2>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
            >
              Delete Project
            </button>
          ) : (
            <div className="flex flex-col gap-3">
              <p className="text-red-600 font-medium">
                Are you sure? This action cannot be undone.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={deleteProject}
                  className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
                >
                  Yes, Delete
                </button>
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="bg-gray-300 px-4 py-2 rounded"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* View-only notice for link users */}
      {isReadOnly && (
        <p className="text-gray-500 italic mt-4">
          You are viewing this project via a shared link. Editing is disabled.
        </p>
      )}
    </div>
  );
}
