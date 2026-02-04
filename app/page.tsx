"use client";

import { useState } from "react";
import Sidebar from "./components/Sidebar";
import Dashboard from "./components/Dashboard";
import Settings from "./components/Settings";
import License from "./components/License";
import type { Page } from "./types";

export default function Home() {
  const [currentPage, setCurrentPage] = useState<Page>("dashboard");

  return (
    <div className="flex h-screen bg-base-300 overflow-hidden">
      <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
      <main className="flex-1 overflow-y-auto">
        {currentPage === "dashboard" && <Dashboard />}
        {currentPage === "settings" && <Settings />}
        {currentPage === "license" && <License />}
      </main>
    </div>
  );
}
