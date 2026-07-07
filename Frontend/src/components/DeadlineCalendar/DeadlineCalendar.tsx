"use client";

import { useMemo, useState } from "react";
import { Calendar, dateFnsLocalizer, View } from "react-big-calendar";
import { format } from "date-fns/format";
import { parse } from "date-fns/parse";
import { startOfWeek } from "date-fns/startOfWeek";
import { getDay } from "date-fns/getDay";
import { enUS } from "date-fns/locale";
import "react-big-calendar/lib/css/react-big-calendar.css";
import styles from "./DeadlineCalendar.module.css";
import CustomToolbar from "./Toolbar";
const locales = {
  "en-US": enUS,
};

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales,
});

interface DeadlineCalendarProps {
  projects: {
    id: string;
    name: string;
    startDate?: string;
    dueDate?: string;
    priority?: "Urgent" | "High" | "Medium" | "Low";
  }[];
}

export default function DeadlineCalendar({ projects }: DeadlineCalendarProps) {
  
  const [date, setDate] = useState(new Date());
  const [view, setView] = useState<View>("month");

  //  Firebase projects into Calendar events
  const events = useMemo(() => {
    return projects
      .filter((p) => p.startDate && p.dueDate)
      .map((p) => ({
        id: p.id,
        title: p.name,
        start: new Date(p.startDate!),
        end: new Date(p.dueDate!),
        priority: p.priority || "Medium",
      }));
  }, [projects]);

  // Style events by priority
 const eventPropGetter = (event: any) => {
  const colors: Record<string, string> = {
    Urgent: "rgba(212, 32, 32, 0.6)", // faint red
    High: "rgba(242, 138, 65, 0.6)",  // faint orange
    Medium: "rgba(234, 179, 8, 0.6)", // faint yellow
    Low: "rgba(120, 113, 108, 0.6)",  // faint gray
  };

  return {
    style: {
      backgroundColor: colors[event.priority] || "rgba(59, 130, 246, 0.25)",
      borderRadius: "6px",
      color: "#000000", 
      border: "1px solid transparent",
      padding: "2px 6px",
      fontSize: "0.85rem",
      fontWeight: 650,
    },
  };
};
  return (
  
    <div className={styles.calendarWrapper}>
  
  {/* ===== Header Section ===== */}
<div className="flex flex-col md:flex-row md:items-start lg:items-center md:justify-between mb-2 gap-2 md:gap-3 lg:gap-4 flex-wrap">
  {/* Left: Heading + Subline */}
  <div className="min-w-[220px] flex-1 md:flex-initial">
    <h2 className="text-2xl sm:text-3xl font-bold text-gray-800 leading-tight mb-1 truncate md:whitespace-normal">
      Project Deadlines Calendar
    </h2>
    <p className="text-sm text-gray-400 leading-snug">
      View all project timelines and priorities in one glance.
    </p>
  </div>

  {/* Right: Legends */}
  <div className="flex flex-wrap items-center justify-start md:justify-end gap-2 sm:gap-3 mt-3 md:mt-0 flex-1 md:flex-none">
    {[
      { label: "Urgent", color: "#d4202099" },
      { label: "High", color: "#f28a4199" },
      { label: "Medium", color: "#eab30899" },
      { label: "Low", color: "#78716c99" },
    ].map((item) => (
      <div
        key={item.label}
        className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-md shadow-sm border border-gray-100 hover:bg-gray-100 transition"
      >
        <span
          className="inline-block w-3 h-3 rounded-full shadow-sm"
          style={{ backgroundColor: item.color }}
        ></span>
        <span className="text-sm font-medium text-gray-700">
          {item.label}
        </span>
      </div>
    ))}
  </div>
</div>


    {/* ===== Calendar Section ===== */}
    <div className="bg-white border-2 border-gray-200 rounded-lg p-4 shadow-inner min-h-[700px] ">
      <Calendar
        localizer={localizer}
        events={events}
        startAccessor="start"
        endAccessor="end"
        views={["month", "week", "day"]}
        popup
        date={date}
        view={view}
        onNavigate={(newDate) => setDate(newDate)}
        onView={(newView) => setView(newView)}
        eventPropGetter={eventPropGetter}
        components={{
          toolbar: CustomToolbar,
        }}
      />
    </div>
  </div>
);

}
