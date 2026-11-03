import type { Metadata } from "next";
import Dashboard from "@/components/Dashboard";
import { readCrm } from "@/lib/crm";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Dashboard — whynot" };

export default function DashboardPage() {
  return <Dashboard crm={readCrm()} />;
}
