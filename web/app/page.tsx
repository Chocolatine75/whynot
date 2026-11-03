import { Mark } from "@/components/Logo";
import SearchBar from "@/components/SearchBar";

export default function Home() {
  return (
    <main className="home" id="content">
      <div className="home-inner">
        <div className="halo" aria-hidden><Mark size={168} animated /></div>
        <h1 className="home-name">why<span>not</span></h1>
        <p className="home-line">Your Meta ads, made and tested before you spend.</p>
        <SearchBar />
      </div>
    </main>
  );
}
