"use client";

import React, { useState } from "react";
import Navbar from "@/components/Navbar";


type Metric = {
  name: string;
  inputs: { label: string; key: string; placeholder: string }[];
  formula: (values: Record<string, number>) => number;
};

const metrics: Metric[] = [
  {
    name: "Defect Density",
    inputs: [
      { label: "Defect Count", key: "defects", placeholder: "e.g., 50" },
      { label: "Lines of Code (LOC)", key: "loc", placeholder: "e.g., 50000" },
    ],
    formula: (v) => v.defects / v.loc,
  },
  {
    name: "Code Coverage",
    inputs: [
      { label: "Lines Tested", key: "tested", placeholder: "e.g., 800" },
      { label: "Total Lines", key: "total", placeholder: "e.g., 1000" },
    ],
    formula: (v) => (v.tested / v.total) * 100,
  },
  {
    name: "Cyclomatic Complexity",
    inputs: [
      { label: "Number of Edges", key: "edges", placeholder: "e.g., 10" },
      { label: "Number of Nodes", key: "nodes", placeholder: "e.g., 8" },
    ],
    formula: (v) => v.edges - v.nodes + 2,
  },
  {
    name: "Mean Time to Repair (MTTR)",
    inputs: [
      {
        label: "Total Downtime (hours)",
        key: "downtime",
        placeholder: "e.g., 40",
      },
      {
        label: "Number of Incidents",
        key: "incidents",
        placeholder: "e.g., 10",
      },
    ],
    formula: (v) => v.downtime / v.incidents,
  },
  {
    name: "Mean Time Between Failures (MTBF)",
    inputs: [
      {
        label: "Total Uptime (hours)",
        key: "uptime",
        placeholder: "e.g., 1000",
      },
      { label: "Number of Failures", key: "failures", placeholder: "e.g., 5" },
    ],
    formula: (v) => v.uptime / v.failures,
  },
  {
    name: "Change Failure Rate",
    inputs: [
      { label: "Failed Changes", key: "failed", placeholder: "e.g., 3" },
      { label: "Total Changes", key: "total", placeholder: "e.g., 10" },
    ],
    formula: (v) => (v.failed / v.total) * 100,
  },
  {
    name: "Customer Reported Defects",
    inputs: [
      { label: "Customer Defects", key: "customer", placeholder: "e.g., 4" },
      { label: "Total Defects", key: "total", placeholder: "e.g., 50" },
    ],
    formula: (v) => (v.customer / v.total) * 100,
  },
  {
    name: "Defect Removal Efficiency",
    inputs: [
      {
        label: "Defects Removed Before Release",
        key: "removed",
        placeholder: "e.g., 40",
      },
      { label: "Total Defects Found", key: "total", placeholder: "e.g., 50" },
    ],
    formula: (v) => (v.removed / v.total) * 100,
  },
];

export default function MetricCalculator() {
  const [selectedMetric, setSelectedMetric] = useState<Metric>(metrics[0]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<number | null>(null);
  const [error, setError] = useState<string>("");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const handleCalculate = () => {
    setError("");
    const numValues: Record<string, number> = {};
    for (const input of selectedMetric.inputs) {
      const val = parseFloat(values[input.key]);
      if (isNaN(val) || val <= 0) {
        setError("Please enter valid positive numbers for all fields.");
        return;
      }
      numValues[input.key] = val;
    }
    const calcResult = selectedMetric.formula(numValues);
    setResult(calcResult);
  };

  return (
    <div className="bg-gradient-to-br from-gray-50 via-purple-50/30 to-blue-50 min-h-screen flex flex-col">
      {/* Navbar */}
      <Navbar />

      {/* Main Content */}
      <main className="flex-grow flex items-center justify-center py-12 px-4">
        <div className="bg-white p-8 rounded-2xl shadow-xl w-full max-w-2xl">
          {/* Heading */}
          <h2 className="text-4xl font-extrabold bg-gradient-to-r from-purple-700 via-purple-900 to-blue-700 bg-clip-text text-transparent text-center">
            Metric Calculator
          </h2>
          <p className="text-gray-500 mt-2 mb-5 text-center">
            Select a metric and enter the required values to calculate the
            result.
          </p>

          {/* Metric Selector */}
          <label className="block font-semibold mb-2 text-gray-800">
            Select Metric
          </label>
          <div className="relative w-full mb-6">
            <button
              onClick={() => setDropdownOpen((prev) => !prev)}
              className="w-full border border-gray-300 rounded-lg p-3 text-gray-800 
              bg-white text-left truncate shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              {selectedMetric.name}
            </button>
            {dropdownOpen && (
              <div className="absolute z-10 mt-2 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-52 overflow-y-auto">
                {metrics.map((metric) => (
                  <div
                    key={metric.name}
                    onClick={() => {
                      setSelectedMetric(metric);
                      setDropdownOpen(false);
                    }}
                    className="px-3 py-2 hover:bg-purple-50 cursor-pointer truncate text-gray-700"
                  >
                    {metric.name}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Inputs */}
          {selectedMetric.inputs.map((input) => (
            <div key={input.key} className="mb-5">
              <label className="block font-medium text-gray-700 mb-1">
                {input.label}
              </label>
              <input
                type="number"
                value={values[input.key] || ""}
                onChange={(e) =>
                  setValues((prev) => ({
                    ...prev,
                    [input.key]: e.target.value,
                  }))
                }
                placeholder={input.placeholder}
                className="w-full border border-gray-300 rounded-lg p-3 shadow-sm 
                focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              />
            </div>
          ))}

          {/* Error */}
          {error && (
            <p className="text-red-600 text-sm font-medium mb-3">{error}</p>
          )}

          {/* Calculate */}
          <button
            onClick={handleCalculate}
            className="w-full bg-gradient-to-r from-purple-700 via-purple-800 to-blue-900 
            hover:opacity-90 font-bold text-white py-3 px-4 rounded-xl shadow-md transition"
          >
            Calculate
          </button>

          {/* Result */}
          {result !== null && !error && (
            <div className="mt-6">
              <h3 className="text-2xl font-bold text-gray-800 mb-2">Result</h3>
              <div className="bg-gray-200 rounded-lg p-4 shadow-inner">
                <p className="text-2xl font-extrabold text-purple-700">
                  {result.toFixed(3)}
                </p>
                <p className="text-sm text-gray-600 mt-1">
                  {selectedMetric.name}
                </p>
              </div>
            </div>
          )}
        </div>
      </main>

    </div>
  );
}
