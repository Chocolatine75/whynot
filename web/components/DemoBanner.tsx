import Link from "next/link";
import { DEMO, DEMO_RUN } from "@/lib/demo";

/** On the public demo, every page says what it is: a read-only example, with what is real and what is simulated. */
export default function DemoBanner() {
  if (!DEMO) return null;
  return (
    <div className="demo-banner" role="note">
      <strong>Read-only demo.</strong>{" "}
      An example campaign whynot made for <strong>Duolingo</strong> from its public App Store page (concept ads, not
      affiliated with Duolingo). Research, strategy, ads, the simulated feed and the evolution are real outputs of the
      engine; the <strong>week of results is simulated</strong> (a labelled model, nothing was spent). Nothing runs
      here and no API key is used.{" "}
      <Link href={`/runs/${DEMO_RUN}`}>Open the campaign</Link>{" · "}
      <a href="https://github.com/Chocolatine75/whynot" target="_blank" rel="noreferrer">Code on GitHub</a>
    </div>
  );
}
