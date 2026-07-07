"use client";

import { useEffect, useState, useMemo } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import { getAuth, onAuthStateChanged, User } from "firebase/auth";
import {
  getFirestore,
  collection,
  query,
  where,
  getDocs,
} from "firebase/firestore";

// Chart colors
const COLORS = ["#4CAF50", "#3B82F6", "#EC4899", "#A855F7"];

interface Project {
  id: string;
  status: "Completed" | "In Progress" | "Not Started" | "On Hold";
}

export default function ChartProjectsStatus() {
  const [data, setData] = useState<{ name: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const auth = getAuth();
    const db = getFirestore();

    const unsubscribe = onAuthStateChanged(auth, async (user: User | null) => {
      if (!user) {
        setError("You must be logged in to see your projects.");
        setLoading(false);
        return;
      }

      try {
        const q = query(
          collection(db, "projects"),
          where("ownerId", "==", user.uid)
        );
        const querySnapshot = await getDocs(q);

        const statusCount: Record<string, number> = {
          Completed: 0,
          "In Progress": 0,
          "Not Started": 0,
          "On Hold": 0,
        };

        querySnapshot.forEach((doc) => {
          const project = doc.data() as Project;
          if (statusCount[project.status] !== undefined) {
            statusCount[project.status] += 1;
          }
        });

        const chartData = Object.entries(statusCount).map(([key, value]) => ({
          name: key,
          value,
        }));

        setData(chartData);
      } catch (err: any) {
        console.error("Error fetching projects:", err);
        setError("Failed to load projects. Check permissions or rules.");
      } finally {
        setLoading(false);
      }
    });

    return () => unsubscribe();
  }, []);

  const totalProjects = useMemo(
    () => data.reduce((sum, item) => sum + item.value, 0),
    [data]
  );

  if (loading)
    return <p className="text-center text-gray-500">Loading chart...</p>;
  if (error) return <p className="text-center text-red-500">{error}</p>;

  return (
    <div className="relative w-full bg-white rounded-2xl shadow-xl p-4  flex flex-col">
      {/* Heading */}

      <h2 className="text-2xl font-bold text-gray-800">Project Status</h2>
      <p className="text-sm text-gray-500 mt-1">
        Projects are grouped by their current phase of development
      </p>

      {/* Chart container */}
      <div className="w-full h-[280px] sm:h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius="75%"
              outerRadius="90%"
              dataKey="value"
              label={({ cx, cy }) => (
                <text
                  x={cx}
                  y={cy}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="fill-gray-800 text-3xl sm:text-4xl font-extrabold"
                >
                  {totalProjects}
                  <tspan
                    x={cx}
                    dy="1.5em"
                    className="fill-gray-400 text-sm font-medium"
                  >
                    Projects
                  </tspan>
                </text>
              )}
              labelLine={false}
            >
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip />

            {/* Custom Legend with 2 on left, 2 on right */}
            <Legend
              content={({ payload }) => {
                if (!payload) return null;
                const leftItems = payload.slice(0, 2);
                const rightItems = payload.slice(2);

                return (
                  <div className="flex justify-between mt-1 text-sm sm:text-base">
                    {/* Left side */}
                    <div className="flex flex-col gap-1.5 items-start">
                      {leftItems.map((entry, idx) => (
                        <div key={idx} className="flex items-center gap-1">
                          <span
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: entry.color }}
                          ></span>
                          <span className="text-gray-700 whitespace-nowrap text-xs sm:text-sm md:text-xs">
                            {entry.value}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Right side */}
                    <div className="flex flex-col gap-1.5 items-end">
                      {rightItems.map((entry, idx) => (
                        <div key={idx} className="flex items-center gap-1">
                          <span
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: entry.color }}
                          ></span>
                          <span className="text-gray-700 whitespace-nowrap text-xs sm:text-sm md:text-xs">
                            {entry.value}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
