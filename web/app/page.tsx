import { Mark } from "@/components/Logo";
import SearchBar from "@/components/SearchBar";
import { fileUrl } from "@/lib/format";
import { showcase } from "@/lib/runs";

export const dynamic = "force-dynamic";

export default function Home() {
  const wall = showcase();
  const rows = [wall.filter((_, i) => i % 2 === 0), wall.filter((_, i) => i % 2 === 1)];
  return (
    <main className="home" id="content">
      <div className="home-inner">
        <div className="logo-stage" aria-hidden>
          <div className="logo-3d"><Mark size={150} /></div>
        </div>
        <h1 className="home-name">whynot</h1>
        <p className="home-line">Your Meta ads, <em>made and tested</em> before you spend.</p>
        <SearchBar />
      </div>
      {wall.length > 3 && (
        <div className="wall" aria-hidden>
          {rows.map((row, r) => (
            <div key={r} className={`wall-row${r ? " rev" : ""}`}>
              {[...row, ...row, ...row, ...row].map((a, i) => ( // two copies of a doubled row: always wider than the screen, loops at -50 %
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
