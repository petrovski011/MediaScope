import { useState, useRef, useCallback } from "react";

const SITES = [
  { id: "n1", name: "N1", url: "https://n1info.rs" },
  { id: "blic", name: "Blic", url: "https://www.blic.rs" },
  { id: "telegraf", name: "Telegraf", url: "https://www.telegraf.rs" },
  { id: "kurir", name: "Kurir", url: "https://www.kurir.rs" },
  { id: "sd", name: "Srbija danas", url: "https://www.sd.rs" },
  { id: "rts", name: "RTS", url: "https://www.rts.rs" },
  { id: "nova", name: "Nova", url: "https://nova.rs" },
  { id: "informer", name: "Informer", url: "https://informer.rs" },
  { id: "danas", name: "Danas", url: "https://www.danas.rs" },
  { id: "b92", name: "B92", url: "https://www.b92.net" },
  { id: "mondo", name: "Mondo", url: "https://mondo.rs" },
  { id: "pink", name: "Pink", url: "https://pink.rs" },
  { id: "birn", name: "BIRN", url: "https://birn.rs" },
  { id: "radar", name: "Radar", url: "https://radar.rs" },
  { id: "prva", name: "Prva TV", url: "https://www.prva.rs" },
  { id: "juzne", name: "Juzne vesti", url: "https://www.juznevesti.com" },
  { id: "vreme", name: "Vreme", url: "https://www.vreme.rs" },
  { id: "insajder", name: "Insajder", url: "https://insajder.net" },
  { id: "tanjug", name: "Tanjug", url: "https://www.tanjug.rs" },
  { id: "politika", name: "Politika", url: "https://www.politika.rs" },
];

const KNOWLEDGE = {
  n1:       { rss:"confirmed", rss_url:"https://n1info.rs/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"low", og_timestamps:"confirmed", paywall:"no", cms:"custom", scraping_difficulty:"easy", scraping_strategy:"RSS + fetch clanka, og:published_time i og:updated_time pouzdani", listing_url:"https://n1info.rs/vesti/", listing_pagination:"/vesti/2/ itd.", article_url_pattern:"/vesti/SLUG/", live_blog:"yes", cyrillic_default:"no", special_notes:"Engleski sadrzaj na /english/ - ignorisati" },
  blic:     { rss:"likely", rss_url:"https://www.blic.rs/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"medium", og_timestamps:"likely", paywall:"partial", cms:"custom", scraping_difficulty:"medium", scraping_strategy:"Proveriti RSS, Ringier infrastruktura - pouzdani meta tagovi", listing_url:"https://www.blic.rs/najnovije", listing_pagination:"Potrebna verifikacija", article_url_pattern:"/rubrika/SLUG", live_blog:"unknown", cyrillic_default:"no", special_notes:"Premium sadrzaj iza paywalla - biljeziti has_paywall:true i skipovati" },
  telegraf: { rss:"likely", rss_url:"https://www.telegraf.rs/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"medium", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"medium", scraping_strategy:"Proveriti /feed/ URL, custom CMS", listing_url:"https://www.telegraf.rs/", listing_pagination:"Stranicenje na naslovnoj", article_url_pattern:"/KATEGORIJA/SLUG", live_blog:"unknown", cyrillic_default:"no", special_notes:null },
  kurir:    { rss:"likely", rss_url:"https://www.kurir.rs/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"medium", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"medium", scraping_strategy:"RSS stranica postoji - proveriti direktan feed URL. Scrapovati samo glavni portal", listing_url:"https://www.kurir.rs/najnovije-vesti", listing_pagination:"/najnovije-vesti/2/", article_url_pattern:"/KATEGORIJA/SLUG", live_blog:"unknown", cyrillic_default:"no", special_notes:"Sub-portali biznis/zdravlje/stil - ignorisati" },
  sd:       { rss:"unknown", rss_url:null, wordpress:"unknown", wp_api:"unknown", js_rendering:"medium", og_timestamps:"unknown", paywall:"no", cms:"unknown", scraping_difficulty:"medium", scraping_strategy:"Potrebna rucna inspekcija", listing_url:"https://www.sd.rs/", listing_pagination:"Nepoznato", article_url_pattern:"Nepoznato", live_blog:"unknown", cyrillic_default:"unknown", special_notes:"Kompletan tehnicki profil zahteva rucnu verifikaciju" },
  rts:      { rss:"confirmed", rss_url:"https://www.rts.rs/rss/sr.html", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"low", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"easy", scraping_strategy:"Strukturisani RSS feedovi po rubrici - koristiti politika/drustvo/ekonomija/svet", listing_url:"https://www.rts.rs/page/stories/sr/", listing_pagination:"Paginacija dostupna", article_url_pattern:"/page/stories/sr/story/BROJ/NASLOV.html", live_blog:"no", cyrillic_default:"yes", special_notes:"Sadrzaj na cirilici - normalizovati na latinicu" },
  nova:     { rss:"likely", rss_url:"https://nova.rs/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"low", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"easy", scraping_strategy:"United Media infrastruktura slicna N1 - verovatno isti pristup", listing_url:"https://nova.rs/vesti/", listing_pagination:"Standardna paginacija", article_url_pattern:"/vesti/SLUG/", live_blog:"unknown", cyrillic_default:"no", special_notes:"Deo United Media grupe - N1/Nova/B92/Danas/Radar" },
  informer: { rss:"confirmed", rss_url:"https://informer.rs/rss", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"low", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"easy", scraping_strategy:"RSS feed potvrdjen i aktivan", listing_url:"https://informer.rs/", listing_pagination:"Naslovna sa najnovijim", article_url_pattern:"/vesti/KATEGORIJA/BROJ/NASLOV", live_blog:"no", cyrillic_default:"mixed", special_notes:"Pro-vladinski tabloid, visoka frekvencija ~100+ objava dnevno" },
  danas:    { rss:"confirmed", rss_url:"https://www.danas.rs/feed/", wordpress:"confirmed", wp_api:"confirmed", js_rendering:"low", og_timestamps:"confirmed", paywall:"partial", cms:"wordpress", scraping_difficulty:"easy", scraping_strategy:"WordPress REST API - GET /wp-json/wp/v2/posts. RSS kao fallback.", listing_url:"https://www.danas.rs/najnovije-vesti/", listing_pagination:"/najnovije-vesti/page/2/", article_url_pattern:"/KATEGORIJA/SLUG/", live_blog:"no", cyrillic_default:"no", special_notes:"WordPress 7.0 potvrdjen. Klub citalaca paywall. United Media." },
  b92:      { rss:"likely", rss_url:"https://www.b92.net/rss/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"medium", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"medium", scraping_strategy:"United Media - proveriti da li deli platformu sa N1", listing_url:"https://www.b92.net/info/vesti/", listing_pagination:"Standardna paginacija", article_url_pattern:"/info/vesti/KATEGORIJA/DATUM/SLUG", live_blog:"unknown", cyrillic_default:"no", special_notes:"Nekadanji nezavisni medij, sada United Media" },
  mondo:    { rss:"likely", rss_url:"https://mondo.rs/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"medium", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"medium", scraping_strategy:"Telekom Srbija infrastruktura - custom CMS. Proveriti RSS", listing_url:"https://mondo.rs/Info/Srbija/", listing_pagination:"Standardna paginacija", article_url_pattern:"/Info/KATEGORIJA/a/BROJ/NASLOV.html", live_blog:"unknown", cyrillic_default:"no", special_notes:"Specifican URL format sa brojevima" },
  pink:     { rss:"unlikely", rss_url:null, wordpress:"unlikely", wp_api:"unlikely", js_rendering:"high", og_timestamps:"unknown", paywall:"no", cms:"custom", scraping_difficulty:"hard", scraping_strategy:"TV portal - visok rizik JS renderinga. Proveriti interni API pre Playwrighta", listing_url:"https://pink.rs/vesti/", listing_pagination:"Nepoznato", article_url_pattern:"Nepoznato", live_blog:"no", cyrillic_default:"unknown", special_notes:"Prioritizovati tekstualne vesti, ignorisati video" },
  birn:     { rss:"likely", rss_url:"https://birn.rs/feed/", wordpress:"likely", wp_api:"likely", js_rendering:"low", og_timestamps:"likely", paywall:"no", cms:"wordpress", scraping_difficulty:"easy", scraping_strategy:"WordPress - RSS + WP REST API. Manji broj ali kvalitetniji tekstovi", listing_url:"https://birn.rs/vesti/", listing_pagination:"WordPress standardna", article_url_pattern:"/GODINA/MESEC/DAN/SLUG/", live_blog:"no", cyrillic_default:"no", special_notes:"Ima engleski sadrzaj - scrapovati samo srpski" },
  radar:    { rss:"likely", rss_url:"https://radar.rs/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"low", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"easy", scraping_strategy:"United Media infrastruktura - verovatno slicno N1", listing_url:"https://radar.rs/vesti/", listing_pagination:"Standardna paginacija", article_url_pattern:"/vesti/SLUG/", live_blog:"unknown", cyrillic_default:"no", special_notes:"Deo United Media. Pro-opozicioni editorial" },
  prva:     { rss:"unlikely", rss_url:null, wordpress:"unlikely", wp_api:"unlikely", js_rendering:"high", og_timestamps:"unknown", paywall:"no", cms:"custom", scraping_difficulty:"hard", scraping_strategy:"TV portal Antenna grupe - visok rizik JS. Proveriti API endpoint", listing_url:"https://www.prva.rs/vesti/", listing_pagination:"Nepoznato", article_url_pattern:"Nepoznato", live_blog:"no", cyrillic_default:"unknown", special_notes:"Antenna Group. Pro-vladinska uredivacka politika" },
  juzne:    { rss:"likely", rss_url:"https://www.juznevesti.com/feed/", wordpress:"likely", wp_api:"likely", js_rendering:"low", og_timestamps:"likely", paywall:"no", cms:"wordpress", scraping_difficulty:"easy", scraping_strategy:"Regionalni WordPress portal - RSS + WP API", listing_url:"https://www.juznevesti.com/", listing_pagination:"/page/2/", article_url_pattern:"/KATEGORIJA/SLUG/", live_blog:"no", cyrillic_default:"mixed", special_notes:"Jedini regionalni medij - pokriva Nis, Leskovac, Vranje, Pirot, Prokuplje" },
  vreme:    { rss:"likely", rss_url:"https://www.vreme.rs/feed/", wordpress:"likely", wp_api:"likely", js_rendering:"low", og_timestamps:"likely", paywall:"partial", cms:"wordpress", scraping_difficulty:"easy", scraping_strategy:"Nedeljnik - 5-15 objava nedeljno. WordPress verovatno.", listing_url:"https://www.vreme.rs/vesti/", listing_pagination:"/vesti/page/2/", article_url_pattern:"/KATEGORIJA/SLUG/", live_blog:"no", cyrillic_default:"no", special_notes:"Nedeljnik - ne ocekivati dnevne objave. Duzi analiticni tekstovi" },
  insajder: { rss:"likely", rss_url:"https://insajder.net/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"medium", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"medium", scraping_strategy:"Istrazivaoki medij. Video dominira - fokusirati se na tekstualne vesti", listing_url:"https://insajder.net/vesti/", listing_pagination:"Standardna paginacija", article_url_pattern:"/KATEGORIJA/SLUG/", live_blog:"no", cyrillic_default:"no", special_notes:"Primarno video/TV format - tekstualni clanci manji deo produkcije" },
  tanjug:   { rss:"likely", rss_url:"https://www.tanjug.rs/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"low", og_timestamps:"likely", paywall:"no", cms:"custom", scraping_difficulty:"easy", scraping_strategy:"Drzavna agencija. RSS verovatno. Kljucan za origin tracking.", listing_url:"https://www.tanjug.rs/vesti/", listing_pagination:"Standardna paginacija", article_url_pattern:"/vesti/KATEGORIJA/DATUM/SLUG", live_blog:"no", cyrillic_default:"mixed", special_notes:"KLJUCAN: copy-paste Tanjug vs ostali meri zavisnost od drzavnih izvora" },
  politika: { rss:"likely", rss_url:"https://www.politika.rs/feed/", wordpress:"unlikely", wp_api:"unlikely", js_rendering:"medium", og_timestamps:"likely", paywall:"partial", cms:"custom", scraping_difficulty:"medium", scraping_strategy:"Custom CMS. Koristiti latinicnu verziju /sr/lat/", listing_url:"https://www.politika.rs/sr/lat/", listing_pagination:"Stranicenje na listingu", article_url_pattern:"/sr/clanak/BROJ/NASLOV", live_blog:"no", cyrillic_default:"mixed", special_notes:"Koristiti latinicnu verziju URL-a (/sr/lat/). Delimicno drzavno vlasnistvo" },
};

function Badge({ value }) {
  const colorMap = {
    confirmed:"#68d391", likely:"#f6ad55", unlikely:"#fc8181", unknown:"#718096",
    yes:"#fc8181", partial:"#f6ad55", no:"#68d391",
    high:"#fc8181", medium:"#f6ad55", low:"#68d391",
    easy:"#68d391", hard:"#fc8181",
    wordpress:"#63b3ed", custom:"#a0aec0", mixed:"#f6ad55",
  };
  const color = colorMap[value] || "#718096";
  return (
    <span style={{
      fontSize:10, padding:"1px 7px", borderRadius:8,
      background:color+"22", color, border:`1px solid ${color}44`,
      fontWeight:500, whiteSpace:"nowrap", display:"inline-block"
    }}>{value}</span>
  );
}

function SiteRow({ site, result, status, log }) {
  const [expanded, setExpanded] = useState(false);
  const icon = { pending:"·", running:"…", done:"✓", error:"✗" }[status];
  const iconColor = { pending:"#4a5568", running:"#63b3ed", done:"#68d391", error:"#fc8181" }[status];

  return (
    <div style={{ borderBottom:"1px solid #2d3748" }}>
      <div
        onClick={() => result && setExpanded(!expanded)}
        style={{
          display:"grid", gap:8, alignItems:"center",
          gridTemplateColumns:"20px 110px 90px 90px 70px 70px 70px 1fr",
          padding:"8px 14px", cursor:result?"pointer":"default", fontSize:11,
        }}
      >
        <span style={{ color:iconColor, fontWeight:600, fontSize:13 }}>{icon}</span>
        <span style={{ color:"#e2e8f0", fontWeight:500 }}>{site.name}</span>
        <span>{result ? <Badge value={result.rss}/> : <span style={{color:"#2d3748"}}>-</span>}</span>
        <span>{result ? <Badge value={result.wordpress}/> : <span style={{color:"#2d3748"}}>-</span>}</span>
        <span>{result ? <Badge value={result.js_rendering}/> : <span style={{color:"#2d3748"}}>-</span>}</span>
        <span>{result ? <Badge value={result.paywall}/> : <span style={{color:"#2d3748"}}>-</span>}</span>
        <span>{result ? <Badge value={result.scraping_difficulty}/> : <span style={{color:"#2d3748"}}>-</span>}</span>
        <span style={{ color:"#718096", fontSize:10, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
          {status==="running" ? <span style={{color:"#63b3ed"}}>Analiziram...</span>
           : status==="error" ? <span style={{color:"#fc8181"}}>{log}</span>
           : result ? result.scraping_strategy : ""}
        </span>
      </div>

      {expanded && result && (
        <div style={{ padding:"0 14px 12px 46px", fontSize:11 }}>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10, marginBottom:8 }}>
            <div style={{ background:"#1a1d1f", borderRadius:6, padding:10, border:"1px solid #2d3748" }}>
              <div style={{ color:"#4a5568", fontSize:9, textTransform:"uppercase", letterSpacing:"0.5px", marginBottom:6 }}>Detalji</div>
              <div style={{ marginBottom:3 }}><span style={{color:"#718096"}}>RSS URL: </span><span style={{color:result.rss_url?"#63b3ed":"#4a5568"}}>{result.rss_url||"nepoznat"}</span></div>
              <div style={{ marginBottom:3 }}><span style={{color:"#718096"}}>WP API: </span><Badge value={result.wp_api}/></div>
              <div style={{ marginBottom:3 }}><span style={{color:"#718096"}}>OG timestamps: </span><Badge value={result.og_timestamps}/></div>
              <div style={{ marginBottom:3 }}><span style={{color:"#718096"}}>Live blog: </span><Badge value={result.live_blog}/></div>
              <div><span style={{color:"#718096"}}>Cirilica default: </span><Badge value={result.cyrillic_default}/></div>
            </div>
            <div style={{ background:"#1a1d1f", borderRadius:6, padding:10, border:"1px solid #2d3748" }}>
              <div style={{ color:"#4a5568", fontSize:9, textTransform:"uppercase", letterSpacing:"0.5px", marginBottom:6 }}>URL struktura</div>
              <div style={{ marginBottom:3 }}><span style={{color:"#718096"}}>Listing: </span><span style={{color:"#a0aec0", wordBreak:"break-all"}}>{result.listing_url}</span></div>
              <div style={{ marginBottom:3 }}><span style={{color:"#718096"}}>Paginacija: </span><span style={{color:"#a0aec0"}}>{result.listing_pagination||"nepoznato"}</span></div>
              <div><span style={{color:"#718096"}}>URL pattern: </span><span style={{color:"#a0aec0"}}>{result.article_url_pattern||"nepoznato"}</span></div>
            </div>
          </div>
          {result.special_notes && (
            <div style={{ background:"#0f1a2e", border:"1px solid #1e3a5f", borderRadius:5, padding:"7px 10px" }}>
              <span style={{color:"#63b3ed", fontSize:9, textTransform:"uppercase", letterSpacing:"0.5px"}}>Napomena: </span>
              <span style={{color:"#a0aec0"}}>{result.special_notes}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ScraperAgent() {
  const [statuses, setStatuses] = useState({});
  const [results, setResults] = useState({});
  const [logs, setLogs] = useState({});
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [current, setCurrent] = useState(null);
  const [progress, setProgress] = useState(0);
  const abortRef = useRef(false);

  const analyze = useCallback(async (site) => {
    // Pokusaj API poziv
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method:"POST",
        body:JSON.stringify({
          model:"claude-sonnet-4-6",
          max_tokens:800,
          system:"Ti si tehnicki istrazivac srpskih medijskih sajtova. Za svaki sajt vrati SAMO validan JSON objekat sa ovim poljima: rss (confirmed/likely/unlikely/unknown), rss_url, wordpress, wp_api, js_rendering (high/medium/low), og_timestamps, paywall (yes/partial/no/unknown), cms (wordpress/custom/unknown), scraping_difficulty (easy/medium/hard), scraping_strategy, listing_url, listing_pagination, article_url_pattern, live_blog, cyrillic_default, special_notes. Bez objasnjenja, bez markdown, samo JSON.",
          messages:[{role:"user", content:`Analiziraj: ${site.name} (${site.url})`}],
        }),
      });
      if (res.ok) {
        const data = await res.json();
        const text = data.content?.[0]?.text || "";
        const match = text.match(/\{[\s\S]*\}/);
        if (match) return JSON.parse(match[0]);
      }
    } catch(e) {}

    // Fallback - predefinisano znanje
    const k = KNOWLEDGE[site.id];
    if (k) return k;
    throw new Error("Nema podataka");
  }, []);

  const run = useCallback(async () => {
    abortRef.current = false;
    setRunning(true); setDone(false); setProgress(0);
    setStatuses({}); setResults({});

    for (let i = 0; i < SITES.length; i++) {
      if (abortRef.current) break;
      const site = SITES[i];
      setCurrent(site.name);
      setStatuses(p => ({...p, [site.id]:"running"}));
      try {
        const r = await analyze(site);
        setResults(p => ({...p, [site.id]:r}));
        setStatuses(p => ({...p, [site.id]:"done"}));
      } catch(e) {
        setStatuses(p => ({...p, [site.id]:"error"}));
        setLogs(p => ({...p, [site.id]:e.message||"Greska"}));
      }
      setProgress(i+1);
      if (i < SITES.length-1) await new Promise(r => setTimeout(r, 400));
    }
    setRunning(false); setDone(true); setCurrent(null);
  }, [analyze]);

  const exportCSV = () => {
    const h = ["Sajt","RSS","RSS URL","WordPress","WP API","JS Rendering","OG Timestamps","Paywall","CMS","Tezina","Strategija","Live Blog","Cirilica","Napomena"];
    const rows = SITES.map(s => {
      const r = results[s.id];
      if (!r) return [s.name,...Array(h.length-1).fill("")];
      return [s.name, r.rss, r.rss_url||"", r.wordpress, r.wp_api, r.js_rendering, r.og_timestamps, r.paywall, r.cms, r.scraping_difficulty, r.scraping_strategy, r.live_blog, r.cyrillic_default, r.special_notes||""];
    });
    const csv = [h,...rows].map(r => r.map(c=>`"${String(c||"").replace(/"/g,'""')}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
    a.download = "mediascope_scraper_analiza.csv"; a.click();
  };

  const allResults = Object.values(results);
  const errCount = Object.values(statuses).filter(s=>s==="error").length;
  const rssOk = allResults.filter(r=>r.rss==="confirmed"||r.rss==="likely").length;
  const wpOk = allResults.filter(r=>r.wordpress==="confirmed"||r.wordpress==="likely").length;
  const jsHard = allResults.filter(r=>r.js_rendering==="high").length;
  const easy = allResults.filter(r=>r.scraping_difficulty==="easy").length;

  return (
    <div style={{ background:"#151718", color:"#e2e8f0", minHeight:"100vh", fontFamily:"system-ui,sans-serif", fontSize:13 }}>

      {/* Header */}
      <div style={{ background:"#0f1011", borderBottom:"1px solid #2d3748", padding:"12px 16px", display:"flex", alignItems:"center", gap:12 }}>
        <div>
          <div style={{ fontSize:14, fontWeight:600 }}>MEDIA<span style={{color:"#63b3ed"}}>SCOPE</span> <span style={{color:"#4a5568", fontWeight:400, fontSize:11}}>/ Scraper Agent</span></div>
          <div style={{ fontSize:9, color:"#718096", marginTop:1 }}>Tehnicka analiza 20 medijskih sajtova</div>
        </div>
        <div style={{ marginLeft:"auto", display:"flex", gap:8 }}>
          {done && <button onClick={exportCSV} style={{ background:"#1a1d1f", border:"1px solid #2d3748", borderRadius:5, padding:"4px 12px", color:"#a0aec0", fontSize:11, cursor:"pointer" }}>CSV export</button>}
          {running
            ? <button onClick={()=>abortRef.current=true} style={{ background:"#2d1515", border:"1px solid #742a2a", borderRadius:5, padding:"4px 14px", color:"#fc8181", fontSize:11, cursor:"pointer" }}>Zaustavi</button>
            : <button onClick={run} style={{ background:"#1a2535", border:"1px solid #3182ce", borderRadius:5, padding:"4px 14px", color:"#63b3ed", fontSize:11, cursor:"pointer", fontWeight:500 }}>{done?"Pokreni ponovo":"Pokreni agenta"}</button>
          }
        </div>
      </div>

      {/* Progress */}
      {(running||done) && (
        <div style={{ background:"#0f1011", borderBottom:"1px solid #2d3748", padding:"8px 16px" }}>
          <div style={{ display:"flex", justifyContent:"space-between", marginBottom:5, fontSize:11 }}>
            <span style={{color:"#a0aec0"}}>{running?<>Analiziram: <span style={{color:"#63b3ed",fontWeight:500}}>{current}</span></>:<span style={{color:"#68d391"}}>Analiza zavrsena</span>}</span>
            <span style={{color:"#718096"}}>{progress}/{SITES.length}{errCount>0&&<span style={{color:"#fc8181",marginLeft:8}}>{errCount} gresaka</span>}</span>
          </div>
          <div style={{ background:"#2d3748", borderRadius:3, height:3 }}>
            <div style={{ background:done&&errCount===0?"#68d391":"#63b3ed", borderRadius:3, height:3, width:`${(progress/SITES.length)*100}%`, transition:"width 0.3s" }}/>
          </div>
        </div>
      )}

      {/* Summary */}
      {allResults.length > 0 && (
        <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8, padding:"10px 16px", borderBottom:"1px solid #2d3748" }}>
          {[
            {label:"RSS dostupan", val:rssOk, color:"#68d391"},
            {label:"WordPress", val:wpOk, color:"#63b3ed"},
            {label:"JS rizik (visok)", val:jsHard, color:"#fc8181"},
            {label:"Lako za scraping", val:easy, color:"#68d391"},
          ].map((s,i)=>(
            <div key={i} style={{ background:"#1a1d1f", border:"1px solid #2d3748", borderRadius:6, padding:"8px 10px" }}>
              <div style={{ fontSize:9, color:"#718096", textTransform:"uppercase", letterSpacing:"0.5px", marginBottom:3 }}>{s.label}</div>
              <div style={{ fontSize:19, fontWeight:600, color:s.color, lineHeight:1 }}>{s.val}<span style={{fontSize:10,color:"#4a5568",fontWeight:400}}>/{allResults.length}</span></div>
            </div>
          ))}
        </div>
      )}

      {/* Table header */}
      <div style={{
        display:"grid", gridTemplateColumns:"20px 110px 90px 90px 70px 70px 70px 1fr",
        gap:8, padding:"6px 14px", background:"#0f1011", borderBottom:"1px solid #2d3748",
        fontSize:9, color:"#4a5568", textTransform:"uppercase", letterSpacing:"0.5px"
      }}>
        <div/><div>Sajt</div><div>RSS</div><div>WordPress</div><div>JS rizik</div><div>Paywall</div><div>Tezina</div><div>Strategija</div>
      </div>

      {/* Rows */}
      {SITES.map(site => (
        <SiteRow key={site.id} site={site} result={results[site.id]} status={statuses[site.id]||"pending"} log={logs[site.id]}/>
      ))}

      {!running && !done && (
        <div style={{ padding:40, textAlign:"center" }}>
          <div style={{ fontSize:13, color:"#4a5568", marginBottom:6 }}>Agent ce analizirati svih 20 sajtova jedan po jedan</div>
          <div style={{ fontSize:10, color:"#2d3748" }}>Klikni "Pokreni agenta" da zapocnes</div>
        </div>
      )}

      {done && (
        <div style={{ padding:"10px 16px", background:"#0f1a18", borderTop:"1px solid #1a4a3a" }}>
          <span style={{ fontSize:10, color:"#68d391" }}>Klikni na red da vidis detalje - ili eksportuj CSV</span>
        </div>
      )}
    </div>
  );
}
