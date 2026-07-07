"use client";

import { useEffect, useState } from "react";
import { auth, db } from "@/firebase/firebaseConfig";
import { doc, getDoc, setDoc } from "firebase/firestore";
import { onAuthStateChanged, User } from "firebase/auth";
import Avatar from "@/components/Avatar";
import { Pencil, Save } from "lucide-react";
import toast from "react-hot-toast";
export default function ProfileForm() {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // editable fields
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [country, setCountry] = useState("Pakistan");
  const [gender, setGender] = useState("");
  const [bio, setBio] = useState("");
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      setUser(currentUser);

      if (currentUser) {
        const docRef = doc(db, "users", currentUser.uid);
        const docSnap = await getDoc(docRef);

        if (docSnap.exists()) {
          const data = docSnap.data();
          setProfile(data);
          setFirstName(data.firstName || "");
          setLastName(data.lastName || "");
          setCountry(data.country || "Pakistan");
          setGender(data.gender || "");
          setBio(data.bio || "");
        } else {
          setProfile({ email: currentUser.email });
        }
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const handleSave = async () => {
    if (!user) return;
    const docRef = doc(db, "users", user.uid);
    await setDoc(
      docRef,
      { firstName, lastName, country, gender, bio, email: user.email },
      { merge: true }
    );

    setProfile((prev: any) => ({
      ...prev,
      firstName,
      lastName,
      country,
      gender,
      bio,
      email: user.email,
    }));

    toast.success("Profile updated successfully!");
    setIsEditing(false);
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-lg text-gray-600">Loading profile...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-lg text-red-600">You are not logged in.</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-3xl bg-white rounded-md shadow-lg p-4 sm:p-8">
      {/* Header Section */}
      <div className="flex items-center justify-between border-b pb-6 mb-6 gap-4">
        <div className="flex items-center gap-3 sm:gap-4 min-w-0">
          <Avatar
            name={`${firstName} ${lastName}`}
            email={profile?.email}
            size="w-12 h-12 sm:w-20 sm:h-20"
          />
          <div className="text-left truncate">
            <h2 className="text-base sm:text-xl font-semibold text-gray-800 truncate">
              {firstName || lastName ? `${firstName} ${lastName}` : "No Name"}
            </h2>
            <p className="text-gray-500 text-xs sm:text-base truncate">
              {profile?.email}
            </p>
          </div>
        </div>

        {!isEditing ? (
          <button
            onClick={() => setIsEditing(true)}
            className="flex-shrink-0 flex items-center gap-2 bg-gray-200 hover:bg-gray-300 text-gray-700 
            px-3 sm:px-4 py-2 rounded-lg shadow text-sm sm:text-base"
          >
            <Pencil className="w-4 h-4" />
            <span className="hidden xs:inline">Edit</span>
          </button>
        ) : (
          <button
            onClick={handleSave}
            className="flex-shrink-0 flex items-center gap-2 bg-blue-500 hover:bg-blue-600 text-white 
            px-3 sm:px-4 py-2 rounded-lg shadow text-sm sm:text-base"
          >
            <Save className="w-4 h-4" />
            <span className="hidden xs:inline">Save Changes</span>
          </button>
        )}
      </div>

      {/* Editable Form */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
        <div>
          <label className="block text-sm text-gray-600 mb-1">First Name</label>
          <input
            type="text"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg text-sm"
            disabled={!isEditing}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Last Name</label>
          <input
            type="text"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg text-sm"
            disabled={!isEditing}
          />
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Country</label>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg text-sm"
            disabled={!isEditing}
          >
             <option>Afghanistan</option>
             <option>Bangladesh</option>
             <option>Bhutan</option>
             <option>India</option>
             <option>Maldives</option>
             <option>Nepal</option>
             <option>Pakistan</option>
             <option>Sri Lanka</option>

          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-600 mb-1">Gender</label>
          <select
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="w-full px-3 py-2 border rounded-lg text-sm"
            disabled={!isEditing}
          >
            <option value="">Select Gender</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>

      {/* Bio */}
      <div className="mt-6">
        <label className="block text-sm text-gray-600 mb-1">Bio</label>
        <textarea
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          className="w-full px-3 py-2 border rounded-lg text-sm resize-y"
          rows={3}
          placeholder="Tell us about yourself..."
          disabled={!isEditing}
        />
      </div>

      {/* Email */}
      <div className="mt-8">
        <h3 className="text-gray-700 font-medium mb-2 text-sm sm:text-base">
          My Email Address
        </h3>
        <div className="flex items-center justify-between bg-gray-50 border rounded-lg px-4 py-3">
          <p className="text-gray-600 text-sm sm:text-base truncate">
            {profile?.email}
          </p>
        </div>
      </div>
    </div>
  );
}
