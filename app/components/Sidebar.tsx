"use client";

import { LayoutDashboard, Settings, KeySquare, Mic } from "lucide-react";
import type { Page } from "../types";

interface SidebarProps {
  currentPage: Page;
  onPageChange: (page: Page) => void;
}

const navItems = [
  { id: "dashboard" as Page, label: "Dashboard", icon: LayoutDashboard },
  { id: "settings" as Page, label: "Settings", icon: Settings },
  { id: "license" as Page, label: "Licencia", icon: KeySquare },
];

export default function Sidebar({ currentPage, onPageChange }: SidebarProps) {
  return (
    <aside className="w-60 bg-base-200 border-r border-base-300 flex flex-col shrink-0">
      {/* Brand */}
      <div className="p-5 border-b border-base-300">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-primary rounded-xl flex items-center justify-center shadow-lg">
            <Mic size={18} className="text-primary-content" />
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight">Dictado</h1>
            <p className="text-xs text-base-content/50">Speech to Text</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3">
        <ul className="menu menu-sm gap-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = currentPage === item.id;
            return (
              <li key={item.id}>
                <button
                  onClick={() => onPageChange(item.id)}
                  className={active ? "active" : ""}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                  {item.id === "license" && (
                    <span className="badge badge-primary badge-sm">PRO</span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User */}
      <div className="p-3 border-t border-base-300">
        <div className="flex items-center gap-3 p-2 rounded-lg hover:bg-base-300 cursor-pointer transition-colors">
          <div className="avatar placeholder">
            <div className="bg-primary text-primary-content w-8 rounded-full">
              <span className="text-xs font-bold">JJ</span>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">Juan José</p>
            <p className="text-xs text-base-content/50">Plan gratuito</p>
          </div>
          <svg
            className="w-4 h-4 opacity-50"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </div>
    </aside>
  );
}
