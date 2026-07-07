"use client";

import { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { getAuth, onAuthStateChanged, User } from "firebase/auth";
import {
  getFirestore,
  collection,
  query,
  where,
  onSnapshot,
  Timestamp,
} from "firebase/firestore";

interface Project {
  id: string;
  createdAt?: Timestamp | null;
  status: "Completed" | "In Progress" | "Not Started" | "On Hold";
}

export default function ProjectsAreaChart() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const auth = getAuth();
    const db = getFirestore();

    let unsubscribeSnapshot: (() => void) | null = null;

    const unsubscribeAuth = onAuthStateChanged(auth, (user: User | null) => {
      if (!user) {
        setError("You must be logged in to see your projects.");
        setData([]);
        setLoading(false);
        return;
      }

      try {
        const q = query(collection(db, "projects"), where("ownerId", "==", user.uid));

        unsubscribeSnapshot = onSnapshot(
          q,
          (querySnapshot) => {
            const projects: Project[] = [];
            querySnapshot.forEach((doc) => {
              projects.push({ ...(doc.data() as Project), id: doc.id });
            });

            const months = [
              "Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
            ];

            const monthlyCounts = months.map((month) => ({
              month,
              added: 0,
              completed: 0,
            }));

            projects.forEach((project) => {
              if (!project.createdAt || !(project.createdAt instanceof Timestamp)) return;

              const date = project.createdAt.toDate();
              const monthName = months[date.getMonth()];
              const monthData = monthlyCounts.find((m) => m.month === monthName);

              if (monthData) {
                monthData.added += 1;
                if (project.status === "Completed") monthData.completed += 1;
              }
            });

            setData(monthlyCounts);
            setLoading(false);
          },
          (err) => {
            console.error("Error listening to projects:", err);
            if (err.code === "permission-denied") {
              setData([]);
            }
            setError("Failed to load projects. Check permissions or rules.");
            setLoading(false);
          }
        );
      } catch (err: any) {
        console.error("Error fetching projects:", err);
        setError("Failed to load projects. Check permissions or rules.");
        setLoading(false);
      }
    });

    return () => {
      unsubscribeAuth(); // cleanup auth listener
      if (unsubscribeSnapshot) unsubscribeSnapshot(); // cleanup projects snapshot listener
    };
  }, []);

  if (loading) return <p className="text-center text-gray-500">Loading chart...</p>;
  if (error) return <p className="text-center text-red-500">{error}</p>;

  return (
    <div className="w-full bg-white rounded-2xl shadow-xl flex flex-col overflow-hidden">
      {/* Heading + Context */}
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="text-2xl font-bold text-gray-800">Track Your Activity</h2>
        <p className="text-sm text-gray-500 mt-1">
          Monitor how many projects you’ve started and completed each month.
        </p>
      </div>

      {/* Legend */}
      <div className="px-6 py-3 flex flex-wrap gap-4 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-purple-600 shadow-sm shadow-purple-400"></span>
          <span className="text-xs sm:text-sm md:text-base text-gray-600 font-medium">Added</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-pink-400 shadow-sm shadow-pink-300"></span>
         <span className="text-xs sm:text-sm md:text-base text-gray-600 font-medium">Completed</span>
        </div>
      </div>

      {/* Chart */}
      <div className="w-full h-[220px] sm:h-[260px] lg:h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 5, right: 20, left: 0, bottom: 10 }}
          >
            <defs>
              <linearGradient id="colorAdded" x1="0" y1="0" x2="0" y2="1">
                <stop offset="10%" stopColor="#9D00FF" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#9D00FF" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorCompleted" x1="0" y1="0" x2="0" y2="1">
                <stop offset="10%" stopColor="#FF66B2" stopOpacity={0.7} />
                <stop offset="95%" stopColor="#FF66B2" stopOpacity={0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="month" stroke="#666" />
            <YAxis
  stroke="#666"
  allowDecimals={false}
  domain={[0, "dataMax + 1"]}
  width={30}
  tickMargin={6}
/>

            <Tooltip />

            <Area
              type="monotone"
              dataKey="added"
              stroke="#9D00FF"
              fillOpacity={1}
              fill="url(#colorAdded)"
              strokeWidth={2}
              dot={false}
            />
            <Area
              type="monotone"
              dataKey="completed"
              stroke="#FF66B2"
              fillOpacity={1}
              fill="url(#colorCompleted)"
              strokeWidth={2}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
