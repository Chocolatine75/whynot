import type { Metadata } from "next";
import Link from "next/link";
import ConnectMeta from "@/components/ConnectMeta";

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
      <ConnectMeta />
    </main>
  );
}
