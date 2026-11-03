import SearchBar from "@/components/SearchBar";

export default function Home() {
  return (
    <main className="home">
      <div className="home-inner">
        <h1>Your Meta ads, <span className="grad">made and tested</span> before you spend.</h1>
        <p className="sub">Paste your app. The agency researches your market, makes your ads, tests them against your competitors and waits for your OK.</p>
        <SearchBar />
        <p className="fineprint">Nothing goes live until you approve · a hard daily cap · every action logged</p>
      </div>
      <footer className="home-foot">
        <span>Built on Muse Wonder, Muse Spark, Muse Spark Open, Muse Image, SAM 3.1</span>
        <span>Simulated results are always labelled</span>
      </footer>
    </main>
  );
}
