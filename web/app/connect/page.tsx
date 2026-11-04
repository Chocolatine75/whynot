import type { Metadata } from "next";
import Link from "next/link";
import AgencySettingsCard from "@/components/AgencySettingsCard";
import ConnectMeta from "@/components/ConnectMeta";
import { DEMO } from "@/lib/demo";

export const metadata: Metadata = { title: "Meta account — whynot" };

export default function ConnectPage() {
  return (
    <main className="page narrow" id="content">
      <div className="page-head">
        <div>
          <h1>Your Meta account</h1>
          <p>Connect once. Then paste an App Store link: the agency researches, makes, tests, publishes and runs your ads
            on this account, within your cap.</p>
        </div>
        <Link href="/" className="btn secondary">New campaign</Link>
      </div>
      <div className="stack" style={{ gap: 16 }}>
        {DEMO ? (
          <div className="card" style={{ padding: 20 }}>
            In the read-only demo there is no Meta account to connect. Locally, this page logs in with Facebook (a
            60-day token, renewed alone), finds the ad account and the Page, and sets the agency&apos;s mode and cap.
          </div>
        ) : (<><ConnectMeta /><AgencySettingsCard /></>)}
      </div>
    </main>
  );
}
