import SearchBar from "@/components/SearchBar";
import { fileUrl } from "@/lib/format";
import { showcase } from "@/lib/runs";

export const dynamic = "force-dynamic";

/** The landing page is the one dark, immersive screen: the name, one line, the search bar, a wall of real ads. */
export default function Home() {
  const wall = showcase();
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
                <img key={`${r}-${i}`} src={fileUrl(a.run, a.path)} alt="" loading="lazy" className={a.path.startsWith("videos/") ? "tall" : ""} />
              ))}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
