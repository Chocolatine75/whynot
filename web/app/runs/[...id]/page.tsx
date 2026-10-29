import { notFound } from "next/navigation";
import AgencyRoom from "@/components/AgencyRoom";
import { RunPathError, readRun } from "@/lib/runs";

export const dynamic = "force-dynamic";

export default async function RunPage({ params }: { params: Promise<{ id: string[] }> }) {
  const { id } = await params;
  const runId = id.map(decodeURIComponent).join("/");
  try {
    return <AgencyRoom initial={readRun(runId)} />;
  } catch (e) {
    if (e instanceof RunPathError) notFound();
    throw e;
  }
}
