import SearchBar from "@/components/SearchBar";
import { fileUrl } from "@/lib/format";
import fs from "node:fs";
import path from "node:path";
import { DEMO, DEMO_ROOT } from "@/lib/demo";
import { showcase } from "@/lib/runs";

/** On the public demo, the wall is the local site's wall: the same pictures in the same order (web/demo/wall.json). */
function demoWall(): { src: string; tall: boolean }[] {
  try {
    const items = JSON.parse(fs.readFileSync(path.join(DEMO_ROOT, "wall.json"), "utf8")) as { file: string; tall: boolean }[];
    return items.map((i) => ({ src: `/demo-wall/${i.file}`, tall: i.tall }));
  } catch { return []; }
}

export const dynamic = "force-dynamic";

/** The landing page is the one dark, immersive screen: the name, one line, the search bar, a wall of real ads. */
export default function Home() {
  const wall = DEMO ? demoWall() : showcase().map((a) => ({ src: fileUrl(a.run, a.path), tall: a.path.startsWith("videos/") }));
  const rows = [wall.filter((_, i) => i % 2 === 0), wall.filter((_, i) => i % 2 === 1)];
  return (
    <main className="home" id="content">
      <div className="backdrop" aria-hidden><i className="b1" /><i className="b2" /><i className="b3" /><i className="grain" /></div>
      <div className="home-inner">
        <h1 className="home-name">whynot</h1>
        <p className="home-line">Your Meta ads, <em>made and tested</em> before you spend.</p>
        <SearchBar />
      </div>
      {wall.length > 3 && (
        <div className="wall" aria-hidden>
          {rows.map((row, r) => (
            <div key={r} className={`wall-row${r ? " rev" : ""}`}>
              {/* two copies of a doubled row: always wider than the screen, loops at −50 % */}
              {[...row, ...row, ...row, ...row].map((a, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img key={`${r}-${i}`} src={a.src} alt="" loading="lazy" className={a.tall ? "tall" : ""} />
              ))}
            </div>
          ))}
        </div>
      )}
      {DEMO && (
        <p className="demo-note">
          Demo: the example run we made on Duolingo, with its week of results simulated. To run whynot on your own
          app, run it locally and connect your Meta account and your Meta AI keys.{" "}
          <a href="https://github.com/Chocolatine75/whynot" target="_blank" rel="noreferrer">Code</a>
        </p>
      )}
    </main>
  );
}
