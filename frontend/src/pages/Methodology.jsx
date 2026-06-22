import { useState, useEffect } from 'react'
import {
  BookOpen, Layers, Tag, Users, Compass, Smile, GitBranch, Share2, Zap,
  EyeOff, Clock, Sunrise, Landmark, RefreshCw, Database, AlertTriangle, Info, Shield,
} from 'lucide-react'

/* ──────────────────────────────────────────────────────────────────────────
   Metodologija — istraživačka referenca za svaku analitičku komponentu.
   Statična stranica (bez API-ja); parametri su usklađeni sa stvarnom
   implementacijom (config.py + pipeline taskovi).
   ────────────────────────────────────────────────────────────────────────── */

const SECTIONS = [
  ['model', 'Analitički model i okvir', Compass],
  ['tema', '1. Tematska klasifikacija', Tag],
  ['ner', '2. Entiteti (NER)', Users],
  ['framing', '3. Framing (tematski specifičan)', Layers],
  ['ose', '4. Pozicioniranje na osama', Compass],
  ['sentiment', '5. Sentiment', Smile],
  ['narativi', '6. Narativi', GitBranch],
  ['koordinacija', '7. Detekcija koordinacije', Share2],
  ['anomalije', '8. Detekcija anomalija', Zap],
  ['silence', '9. Silence analiza', EyeOff],
  ['origin', '10. Origin tracking', Clock],
  ['intraday', '11. Intra-day analiza', Sunrise],
  ['politicka', '12. Politička analiza', Landmark],
  ['kalibracija', '13. Kalibracija (RLHF)', RefreshCw],
  ['izvori', '14. Izvori, modeli i parametri', Database],
  ['ograde', '15. Ograničenja i ograde', AlertTriangle],
]

const C = {
  surface: 'var(--bg-surface)', border: 'var(--border)', elevated: 'var(--bg-elevated)',
  primary: 'var(--text-primary)', secondary: 'var(--text-secondary)', muted: 'var(--text-muted)',
  accent: 'var(--accent)',
}

function Section({ id, icon: Icon, title, children }) {
  return (
    <section id={id} className="rounded-xl border p-5"
      style={{ background: C.surface, borderColor: C.border, scrollMarginTop: 24 }}>
      <h2 className="flex items-center gap-2 text-base font-semibold mb-3" style={{ color: C.primary }}>
        <Icon size={17} style={{ color: C.accent }} /> {title}
      </h2>
      <div className="space-y-3 text-sm leading-relaxed" style={{ color: C.secondary }}>{children}</div>
    </section>
  )
}

function Note({ kind = 'info', children }) {
  const styles = ({
    info: { bg: 'rgba(59,130,246,0.08)', bd: 'rgba(59,130,246,0.3)', fg: '#93c5fd', Icon: Info },
    warn: { bg: 'rgba(245,158,11,0.08)', bd: 'rgba(245,158,11,0.3)', fg: '#fbbf24', Icon: AlertTriangle },
    meth: { bg: 'rgba(139,92,246,0.08)', bd: 'rgba(139,92,246,0.3)', fg: '#a78bfa', Icon: Shield },
  }[kind]) ?? { bg: 'rgba(59,130,246,0.08)', bd: 'rgba(59,130,246,0.3)', fg: '#93c5fd', Icon: Info }
  const { Icon } = styles
  return (
    <div className="rounded-lg p-3 flex items-start gap-2 text-xs" style={{ background: styles.bg, border: `1px solid ${styles.bd}`, color: styles.fg }}>
      <Icon size={14} className="mt-0.5 shrink-0" /> <div>{children}</div>
    </div>
  )
}

function Defn({ term, children }) {
  return (
    <div className="rounded-lg p-3" style={{ background: C.elevated }}>
      <span className="font-medium" style={{ color: C.primary }}>{term}</span>
      <div className="text-xs mt-1" style={{ color: C.muted }}>{children}</div>
    </div>
  )
}

function ParamTable({ rows }) {
  return (
    <div className="rounded-lg border overflow-hidden" style={{ borderColor: C.border }}>
      <table className="w-full text-xs">
        <tbody>
          {rows.map(([k, v], i) => (
            <tr key={i} className="border-b last:border-b-0" style={{ borderColor: C.border }}>
              <td className="px-3 py-2 font-mono align-top" style={{ color: C.primary, width: '42%' }}>{k}</td>
              <td className="px-3 py-2" style={{ color: C.muted }}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TOC({ active }) {
  return (
    <nav className="hidden lg:block sticky top-6 self-start w-60 shrink-0">
      <div className="rounded-xl border p-3" style={{ background: C.surface, borderColor: C.border }}>
        <div className="text-xs font-semibold uppercase tracking-wider mb-2 px-2" style={{ color: C.muted }}>Sadržaj</div>
        <ul className="space-y-0.5">
          {SECTIONS.map(([id, title]) => (
            <li key={id}>
              <a href={`#${id}`}
                className="block px-2 py-1 rounded text-xs transition-colors"
                style={{
                  color: active === id ? 'white' : C.secondary,
                  background: active === id ? C.accent : 'transparent',
                }}>
                {title}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}

export default function Methodology() {
  const [active, setActive] = useState('model')

  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => { if (e.isIntersecting) setActive(e.target.id) })
      },
      { rootMargin: '-20% 0px -70% 0px' },
    )
    SECTIONS.forEach(([id]) => {
      const el = document.getElementById(id)
      if (el) obs.observe(el)
    })
    return () => obs.disconnect()
  }, [])

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-5">
        <h1 className="text-lg font-semibold flex items-center gap-2" style={{ color: C.primary }}>
          <BookOpen size={18} style={{ color: C.accent }} /> Metodologija
        </h1>
        <p className="text-sm mt-0.5" style={{ color: C.muted }}>
          Kako svaka analiza meri ono što meri — pristup, podaci, parametri i ograničenja.
          Usklađeno sa stvarnom implementacijom pipeline-a.
        </p>
      </div>

      <div className="flex gap-6 items-start">
        <TOC active={active} />

        <div className="flex-1 min-w-0 space-y-4">

          <Section id="model" icon={Compass} title="Analitički model i teorijski okvir">
            <p>
              MediaScope koristi <strong>četvoronivovski analitički model</strong> koji razdvaja različite
              nivoe medijskog delovanja. Svaki nivo je empirijski potkrepljen dostupnim podacima
              (analiza ~3.000 članaka sa 19 portala).
            </p>
            <div className="grid sm:grid-cols-2 gap-2">
              <Defn term="Nivo 1 — Događaj">Sirova, verifikovana činjenica. Analitički neutralna polazna tačka.</Defn>
              <Defn term="Nivo 2 — Tema">Medijska odluka da li i koliko izveštavati (agenda-setting). Sama selekcija je podatak — koje medije ignorišu temu jednako je važno kao ko je pokriva.</Defn>
              <Defn term="Nivo 3 — Framing">Način predstavljanja teme. Isti događaj može biti uokviren različito (selekcija aspekata i njihovo isticanje).</Defn>
              <Defn term="Nivo 4 — Narativ">Longitudinalni, ponavljajući obrazac framinga koji gradi koherentnu priču kroz stotine tekstova i kroz vreme.</Defn>
            </div>
            <p className="text-xs" style={{ color: C.muted }}>
              <strong>Teorijski okvir:</strong> Entman (1993) za framing; McCombs &amp; Shaw (agenda-setting);
              Miskimmon, O'Loughlin &amp; Roselle (2013) za strateške narative.
            </p>
            <Note kind="info">
              <strong>AI sloj:</strong> per-članak analizu radi <strong>Claude (Anthropic)</strong> kroz noćni Batch API.
              Semantičku sličnost računa <strong>lokalni embedding model</strong> (<code>intfloat/multilingual-e5-base</code>,
              768 dimenzija) — tekst članaka <strong>ne napušta infrastrukturu SHARE-a</strong>.
              Svaka AI klasifikacija nosi <strong>confidence skor</strong> i, gde je primenljivo, <strong>citat iz teksta</strong> (supporting_text) i kratko obrazloženje — radi transparentnosti i proverljivosti.
            </Note>
          </Section>

          <Section id="tema" icon={Tag} title="1. Tematska klasifikacija">
            <p>Svaki članak se svrstava u <strong>jednu primarnu</strong> i do tri sekundarne teme, sa confidence skorom (0–1) i kratkim obrazloženjem.</p>
            <p><strong>Skup tema (17):</strong> POLITIKA, EU_INTEGRACIJE, KOSOVO, EKONOMIJA, INFRASTRUKTURA, BEZBEDNOST, MEDIJSKE_SLOBODE, PROTEST, KULTURA, ZABAVA_I_ESTRADA, SPORT, HRONIKA, ZDRAVLJE, OBRAZOVANJE, SPOLJNA_POLITIKA, LOKALNA_VLAST, DRUSTVO.</p>
            <p className="text-xs" style={{ color: C.muted }}><strong>KULTURA</strong> pokriva pozorište, film, književnost i likovne umetnosti. <strong>ZABAVA_I_ESTRADA</strong> pokriva rijaliti TV, celebrity, folk, showbiz i humor — razdvojenost obezbjeđuje preciznost agregata po temi.</p>
            <p>Klasifikacija je <strong>dinamička</strong>: ako sadržaj ne odgovara nijednoj kategoriji, AI predlaže novu (<code>NOVA_TEMA: …</code>), koju istraživač može usvojiti.</p>
            <p className="text-xs" style={{ color: C.muted }}>Osnova: naslov (100%) + tekst (98.5%) — potpuna podrška za sve izvore.</p>
          </Section>

          <Section id="ner" icon={Users} title="2. Prepoznavanje entiteta (NER)">
            <p>Iz svakog teksta ekstrahuju se <strong>osobe, organizacije i mesta</strong>. Varijante istog entiteta se normalizuju (npr. „Vučić", „Aleksandar Vučić", „predsednik" → <em>Aleksandar Vučić</em>). Generički pojmovi („vlada", „novinari") se izostavljaju.</p>
            <p>Za svaki entitet beleži se: broj pominjanja, da li je <strong>citiran</strong> (is_quoted), da li je <strong>subjekt</strong> članka (is_subject) i da li je <strong>politički akter</strong> (is_political_actor — funkcioner, stranka, institucija).</p>
            <p><strong>Entitetski sentiment</strong> — za svaki politički akter u tekstu, AI procenjuje kako je akter pominjut (−1 negativno, 0 neutralno, +1 pozitivno). Ovo je namerno odvojeno od opšteg sentimenta teksta: isti negativan tekst može pozitivno pominjati jednog aktera i negativno drugog.</p>
            <p className="text-xs" style={{ color: C.muted }}>NER je osnova političke analize: ko se citira, ko se pominje i u kom kontekstu — direktan pokazatelj medijskog tretmana aktera.</p>
            <p><strong>Citati i revizija</strong> — za svaki entitet istraživač može da otvori <strong>kontekstualne citate</strong> (konkretni isečci iz članaka uz izvor, datum i entitetski sentiment) i da po potrebi <strong>izmeni</strong> entitet (naziv, tip, oznaku političkog aktera). Time se ručno koriguju greške NER normalizacije.</p>
          </Section>

          <Section id="framing" icon={Layers} title="3. Framing analiza (tematski specifična)">
            <p><strong>Centralno metodološko načelo:</strong> framing tipovi su <strong>tematski specifični</strong>, ne globalni. Okviri za temu „protesti" potpuno se razlikuju od okvira za „Kosovo". Jedan članak može nositi <strong>više okvira istovremeno</strong>.</p>
            <p>Pri analizi, modelu se prosleđuje <strong>katalog okvira</strong> (keširan blok): globalni okviri (važe za svaku temu) + okviri specifični za temu koju je model upravo odredio. Model bira samo iz tog skupa; za svaki okvir vraća <strong>confidence + citat (supporting_text)</strong>.</p>
            <div className="grid sm:grid-cols-2 gap-2">
              <Defn term="Globalni okviri">threat (pretnja), conflict (sukob), victim (žrtva), progress (napredak), morality (moralni sud).</Defn>
              <Defn term="PROTEST (primer)">huliganstvo, strani_projekat, demokratski_izraz, marginalizacija.</Defn>
              <Defn term="KOSOVO (primer)">suverenitet, izdaja, stabilnost/dijalog, ugroženi Srbi.</Defn>
              <Defn term="EU_INTEGRACIJE (primer)">uslovljavanje, evropski_put, licemerje, reforme.</Defn>
            </div>
            <Note kind="info">
              Ako AI prepozna jasno prisutan okvir koji nije u katalogu, <strong>predlaže nov</strong> — istraživač ga validira pre nego što uđe u upotrebu. Tako se tipologija razvija empirijski, uz ljudskom kontrolom. Upravljanje okvirima je na stranici <em>Framing</em>. Na stranici <em>Teme</em>, framing distribucija za svaku temu prikazuje broj članaka po okviru — svaki bar je <strong>klikabilan</strong> i filtrira članke po temi + framing tipu.
            </Note>
          </Section>

          <Section id="ose" icon={Compass} title="4. Pozicioniranje na analitičkim osama">
            <p>Svaki tekst se pozicionira na dve nezavisne ose plus senzacionalizam. Skorovi se računaju <strong>dinamički iz sadržaja</strong> — ne predefinisano po mediju — i svaki nosi obrazloženje sa konkretnim signalima iz teksta.</p>
            <div className="space-y-2">
              <Defn term="Politička osa (−1.0 … +1.0)">−1 izrazito opoziciono, 0 neutralno, +1 izrazito pro-vladino. Objektivna mera <em>kako</em> tekst pozicionira vladajuću strukturu — ne procena „ispravnosti" stava.</Defn>
              <Defn term="Vrednosna osa (−1.0 … +1.0)">−1 progresivno, 0 neutralno, +1 konzervativno. Vrednosni okvir, nezavisan od politike.</Defn>
              <Defn term="Senzacionalizam (0.0 … 1.0)">0 faktografski, 1 izrazito senzacionalistički (naslov + ton).</Defn>
            </div>
            <p className="text-xs" style={{ color: C.muted }}>Signali: izbor reči, citiranje izvora, selekcija činjenica, naslovi, emotivni naboj.</p>
          </Section>

          <Section id="sentiment" icon={Smile} title="5. Sentiment">
            <p>Tonalitet teksta: kategorija (<strong>positive / negative / neutral / mixed</strong>) + numerički skor (−1.0 … +1.0). Razdvojeno od političke ose — negativan ton ne znači opoziciono pozicioniranje i obrnuto.</p>
          </Section>

          <Section id="narativi" icon={GitBranch} title="6. Narativna analiza">
            <p>Narativ je longitudinalni obrazac vidljiv tek kroz agregaciju. Proces ima četiri koraka:</p>
            <ol className="list-decimal pl-5 space-y-1">
              <li><strong>Seeding:</strong> AI analizira istorijski korpus naslova i predlaže 10–20 narativa (sistemski/tematski) sa opisom i primerima — upisani kao <em>nevalidirani</em>.</li>
              <li><strong>Validacija:</strong> istraživač pregleda i potvrđuje/odbija predloge (ili ručno dodaje svoje).</li>
              <li><strong>Mapiranje:</strong> svaki novi članak se AI-jem mapira <strong>samo na validirane narative</strong> (confidence + citat); off-katalog narativi se predlažu.</li>
              <li><strong>Intenzitet:</strong> dnevni intenzitet narativa po izvoru i datumu (broj članaka × prosečna pouzdanost).</li>
            </ol>
            <div className="grid sm:grid-cols-2 gap-2">
              <Defn term="Sistemski narativ">Sveobuhvatan, dugoročan; provlači se kroz teme (npr. „Srbija kao opkoljena zemlja").</Defn>
              <Defn term="Tematski narativ">Vezan za konkretan događaj (npr. „Protesti kao strani projekat").</Defn>
            </div>
            <Note kind="warn">
              Mapiranje koristi <strong>AI</strong> (značenje, kontekst), a ne prosto poklapanje ključnih reči — pa hvata narativ i kad nije eksplicitan. Jedan članak može nositi više narativa.
            </Note>
            <p><strong>Predloženi narativi se klasterišu semantički</strong> (embedding + kosinusna udaljenost): umesto da se isti koncept formulisan na 50 načina pojavi kao 50 zasebnih predloga, srodne formulacije se spajaju u jedan klaster. Predlog postaje vidljiv istraživaču tek kada klaster obuhvati više nezavisnih članaka — čime se izbegava šum.</p>
            <Note kind="info">
              Kad istraživač <strong>odobri klaster</strong>, svi članci koji su inicirali taj predlog automatski se upisuju u <code>article_narratives</code> (backfill). Narativ odmah pokazuje tačan broj i sadržaj izvornih članaka bez potrebe za ponovnom analizom.
            </Note>
            <p><strong>Reverzibilnost i trag odluka.</strong> Svaka istraživačka odluka (prihvatanje/odbijanje narativa, framinga ili teme, validacija, izmena entiteta) upisuje se u <em>Istraživački log</em> sa starim i novim statusom. Odluke o predlozima i validacijama su <strong>jednoklik-reverzibilne</strong> — vraćaju stavku u prethodno stanje; izmene entiteta se ispravljaju ponovnim editovanjem. Time je ceo proces ljudske kuracije transparentan i poništiv.</p>
          </Section>

          <Section id="koordinacija" icon={Share2} title="7. Detekcija koordinisanog ponašanja">
            <p>Tri nivoa koordinacije između medija:</p>
            <div className="space-y-2">
              <Defn term="Nivo 1 — Copy-paste (semantički)">
                Visoka tekstualna sličnost preko <strong>pgvector cosine</strong> nad lokalnim embeddingima (ne samo poklapanje naslova).
                Prag <code>0.85</code>; alert na <code>0.92</code> između različitih vlasničkih grupa; prozor <code>48h</code>. Hvata parafrazu i agencijski preuzet tekst. Grupe se formiraju <strong>Union-Find algoritmom</strong> — prikazuju se svi mediji unutar grupe (bez ograničenja broja), što omogućava uvid u pun doseg koordinisanog sadržaja.
              </Defn>
              <Defn term="Nivo 2 — Framing koordinacija">
                Različiti tekstovi, ista tema + isti okvir, ≥3 izvora u 24h. Indikator usklađenog uređivačkog pristupa bez deljenja teksta. Prag skora <code>0.70</code>.
              </Defn>
              <Defn term="Nivo 3 — Narativna koordinacija">
                Isti narativ plasiran kroz ≥3 izvora u 48h, čak i kad su teme različite. Prag skora <code>0.75</code>; jaka cross-group koordinacija → alert.
              </Defn>
            </div>
            <p><strong>Mreža koordinacije</strong> agregira sva tri signala u graf (čvorovi = izvori, ivice = jačina). <strong>Vlasnički kontekst</strong> je ključan: koordinacija unutar iste vlasničke grupe ima drugačiju interpretaciju nego između grupa (ivice iste grupe se posebno označavaju). Grupe u sistemu: <em>Adria News Network</em> (N1, Nova S, Danas, Radar — bivša United Media), <em>Kopernikus Media</em> (B92, Prva), <em>Ringier</em> (Blic), <em>Telekom Srbija</em> (Mondo) i dr. SNA matrice (Mediji ↔ Akteri, Teme, Narativi) dostupne su na posebnim tabovima.</p>
            <p>Na nivou pojedinačnog članka, „slični članci" se prikazuju kao <strong>vremenski timeline</strong> (poređani po vremenu objave) — vizuelno otkriva ko je prvi objavio i kako se sadržaj širio kroz izvore. Članci bez tačnog vremena objave prikazuju se odvojeno.</p>
            <Note kind="warn">
              <strong>Koordinacija ne dokazuje nameru.</strong> Sličnost može biti rezultat deljenja istog izvora, prenosa agencijskih vesti ili slučajnog poklapanja. Interpretacija ostaje na istraživaču.
            </Note>
          </Section>

          <Section id="anomalije" icon={Zap} title="8. Detekcija anomalija">
            <p>Statistička (ne-AI) detekcija odstupanja od <strong>rolling baseline-a (7/30 dana)</strong>:</p>
            <ul className="list-disc pl-5 space-y-1">
              <li><strong>Topic spike/drop:</strong> tema ima ≥2.5× više članaka od 7-dnevnog proseka (visoko: ≥3.5×), ili pad na ≤0.34×.</li>
              <li><strong>Framing shift:</strong> dominantni okvir za temu menja udeo &gt;30 procentnih poena.</li>
              <li><strong>Narativni intenzitet:</strong> dnevni intenzitet ≥1.5× (visoko: ≥3×) 7-dnevnog proseka.</li>
            </ul>
            <p>Anomalije se upisuju sa baseline/detektovanom vrednošću i odstupanjem; visoka odstupanja generišu alert.</p>
            <Note kind="info">
              <strong>Period typing:</strong> istraživač označava periode (izborni/krizni/miran). Detektor anotira anomalije tim kontekstom — da se očekivani izborni skokovi ne čitaju pogrešno.
            </Note>
          </Section>

          <Section id="silence" icon={EyeOff} title="9. Silence analiza">
            <p>Jedan od <strong>metodološki najvažnijih</strong> slojeva: šta mediji <strong>biraju da NE pokriju</strong>. Izvor je „tih" na temi ako ima <strong>0 članaka</strong> dok tema ima ≥5 članaka kroz ≥3 druga izvora.</p>
            <p>Coverage matrica pokazuje pokrivenost po izvoru (sa vlasništvom, prosečnim političkim skorom, dominantnim okvirom), a tihi izvori se eksplicitno izdvajaju.</p>
            <Note kind="info">Tišina se računa samo nad skrejpovanim i analiziranim člancima; odsustvo pokrivenosti ne mora značiti namernu cenzuru.</Note>
          </Section>

          <Section id="origin" icon={Clock} title="10. Origin tracking">
            <p>Prati <strong>ko je prvi objavio</strong> temu ili narativ i kako se širio kroz medijski prostor (broj izvora, vreme širenja).</p>
            <div className="space-y-2">
              <Defn term="Origin tema (detect_origin)">Noćni task koji identifikuje koji izvor je prvi objavio određenu temu u zadatom prozoru. Prikazuje se na stranici svakog članka kao „Poreklo priče — ko je objavio prvi" (hronološki timeline s numerisanim pozicijama, prvi izvor istaknuto).</Defn>
              <Defn term="Origin narativa (detect_narrative_origin)">Noćni task koji prati kojim redosledom je svaki <strong>validovani narativ</strong> prošao kroz izvore. Čuva se u tabeli <code>narrative_origin_tracking</code>; dostupno na stranici Narativi → dropdown izaberi narativ → panel porekla. Zahteva ≥2 izvora u 14-dnevnom prozoru. Ako preračunati podaci još nisu dostupni (task još nije pokrenuo), endpoint automatski računa poreklo <strong>uživo iz <code>article_narratives</code></strong> — u tom slučaju <code>computed_at</code> je NULL i UI prikazuje napomenu.</Defn>
            </div>
            <Note kind="info">
              Svi aktivni izvori (uključujući RTS i Tanjug) imaju tačne timestamps od juna 2026. — RTS putem RSS feed-a, Tanjug putem <code>article:published_time</code> meta taga. Ako je <code>published_at</code> nepoznat (NULL za starije arhivske članke), redosled unutar dana se <strong>ne tvrdi</strong> i UI to eksplicitno označava.
            </Note>
            <p className="text-xs" style={{ color: C.muted }}>Stariji RTS i Tanjug članci (pre juna 2026.) imaju NULL published_at i isključeni su iz temporalne analize. <code>detect_narrative_origin</code> se pokreće noćno u 03:20.</p>
          </Section>

          <Section id="intraday" icon={Sunrise} title="11. Intra-day analiza">
            <p>Distribucija tema i narativa kroz delove dana i dane u nedelji. Prikazuje se raspodela po satu (0–23), danu u nedelji (pon–ned) i heatmap (sat × dan). Cilj: identifikovati <strong>strategiju plasiranja narativa</strong> — da li se određeni narativi pojavljuju konsistentno u istim vremenskim prozorima. Članci bez tačnog <code>published_at</code> (RTS, Tanjug — datum bez vremena) se isključuju. Endpoint <code>/intraday/narratives</code> koristi 30-dnevni prozor po difoultu.</p>
            <Note kind="meth">Dnevni AI pregled (07:00) uključuje raspodelu narativa po delovima dana (jutro/podne/veče/noć) samo za izvore sa tačnim vremenom — navedeno u sekciji „Narativi po delovima dana".</Note>
          </Section>

          <Section id="politicka" icon={Landmark} title="12. Politička analiza i propaganda detekcija">
            <p>Specijalizovani objektiv nad istim podacima — kako se politički akteri tretiraju i koje narative projektuju.</p>
            <div className="space-y-2">
              <Defn term="Narativni akteri">Politički akteri (iz NER-a) sa <strong>entitetskim sentimentom</strong> (kako je svaki akter specifično pominjut, −1…+1), brojem pominjanja i distribucijom po alignment-u izvora (pro-vlada / opozicija / neutralno).</Defn>
              <Defn term="Propaganda detekcija (proširena)">
                AI detektuje propagandne tehnike po tekstu: DEMONIZACIJA, DEZINFORMACIJA, CONSPIRACY_THEORY, FEAR_APPEAL, FALSE_DICHOTOMY, SCAPEGOATING, DEFAMATION, SMEAR_CAMPAIGN, WHATABOUTISM, CHERRY_PICKING, EMOTIONAL_APPEAL, <strong>FAR_RIGHT_NARRATIVE, ULTRA_RIGHT_NARRATIVE</strong>. Vraća listu tehnika, confidence (0–1), mete (<code>propaganda_targets</code> sa kategorijom: civil_society|opposition|students|media|other) i novu kolonu <code>geopolitical_sentiment</code>.
              </Defn>
              <Defn term="Geopolitički sentiment">
                Poseban izlaz AI analize (ne ukupni sentiment teksta): kako tekst prikazuje svaki od ključnih geopolitičkih aktera — EU, Rusija, SAD, Kina, NATO, Zapad — na skali −1…+1. Agregira se po akteru u <code>/political/geopolitical</code> endpointu. Popunjava se samo na novim člancima (stari nemaju ovu kolonu).
              </Defn>
            </div>
            <Note kind="warn">
              <strong>Propaganda detekcija je eksperimentalna</strong> — model detektuje površinski/tekstualne signale, ne intenciju autora. Lažno pozitivni su mogući. Interpretacija nalaza ostaje isključivo na istraživaču. Korelacija sa izvorom ≠ dokaz koordinirane propagandne kampanje.
            </Note>
            <p className="text-xs" style={{ color: C.muted }}>Napomena: raniji „narod vs. elite" (populistički meta-framing) je uklonjen iz analize jer je bio nedovoljno precizan.</p>
            <p><strong>Akteri kao ulaz u korpus</strong> — klikom na aktera (ili na polaritet pozitivno/neutralno/negativno) otvara se filtrirana lista članaka u kojima je taj akter tako prikazan. Svaka <strong>propagandna tehnika je klikabilna</strong> → filtrira članke po toj tehnici (<code>/articles?propaganda_technique=X</code>), čime se svaki nalaz može direktno verifikovati na izvornom tekstu.</p>
          </Section>

          <Section id="kalibracija" icon={RefreshCw} title="13. Kalibracija (RLHF)">
            <p>Model kalibracije zasnovan na povratnoj informaciji istraživača (princip RLHF prilagođen istraživanju):</p>
            <ol className="list-decimal pl-5 space-y-1">
              <li>Istraživač daje <strong>thumbs up/down</strong> na klasifikaciju, uz komentar šta nije ispravno.</li>
              <li>Sistem agregira feedback i upisuje <strong>versioniranu kalibracionu instrukciju</strong> (<code>calibration_prompts</code>), koja preživljava restart i deli se među svim workerima.</li>
              <li>Instrukcija se dodaje u sistemski prompt za sve buduće analize.</li>
              <li>Pokreće se <strong>re-analiza embedding-sličnih članaka</strong> onima koji su korigovani (do 200 po ciklusu).</li>
            </ol>
            <p className="text-xs" style={{ color: C.muted }}>Ovo je „soft" kalibracija — kontekstualizacija prompta primerima, ne fine-tuning modela.</p>
          </Section>

          <Section id="izvori" icon={Database} title="14. Izvori, modeli i parametri">
            <p><strong>19 aktivnih portala</strong> (+ Južne vesti kao stub). Vlasnička dimenzija je kontekstualni sloj — grupe: Adria News Network (N1, Nova S, Danas, Radar), Kopernikus Media (B92, Prva), Ringier (Blic), Telekom Srbija/državno (Mondo), Privatni srpski (Telegraf, Kurir, Informer, Tanjug, Srbija danas), Nezavisni/NGO (BIRN, Insajder).</p>
            <p className="font-medium" style={{ color: C.primary }}>Modeli</p>
            <ParamTable rows={[
              ['AI analiza', 'Claude (Anthropic), noćni Batch API (~50% jeftiniji)'],
              ['Embeddings', 'intfloat/multilingual-e5-base — 768d, lokalno (CPU)'],
              ['Ritam', 'noćni batch 22:30 · provera /15min · agregacije i origin/koordinacija u ranim satima · dnevni pregled 07:00 (analizira juče)'],
            ]} />
            <p className="font-medium mt-2" style={{ color: C.primary }}>Ključni pragovi (iz konfiguracije)</p>
            <ParamTable rows={[
              ['COPYPASTE_THRESHOLD', '0.85 (alert: 0.92)'],
              ['COPYPASTE_WINDOW_HOURS', '48'],
              ['FRAMING_COORD_MIN_SCORE', '0.70 (≥3 izvora, 24h)'],
              ['NARRATIVE_COORD_MIN_SCORE', '0.75 (≥3 izvora, 48h)'],
              ['Anomalije baseline', 'rolling 7 / 30 dana'],
              ['Silence', '≥5 članaka kroz ≥3 izvora; izvor sa 0 = tih'],
              ['Kalibracija', 'nedeljno; re-analiza ≤200; sličnost ≥0.88'],
              ['SIMILAR_ARTICLES_THRESHOLD', '0.80 (slični članci)'],
              ['Intra-day / origin', 'svi izvori uključeni; članci bez published_at preskočeni'],
            ]} />
          </Section>

          <Section id="ograde" icon={AlertTriangle} title="15. Ograničenja i metodološke ograde">
            <ul className="list-disc pl-5 space-y-1.5">
              <li><strong>Starija arhiva RTS/Tanjug</strong> (pre juna 2026.) nema tačno vreme objave — ti članci imaju <code>published_at = NULL</code> i isključeni su iz temporalne analize. Novi članci oba izvora imaju tačne timestamps.</li>
              <li><strong>Korelacija ≠ namera.</strong> Koordinacija i poklapanja su signali, ne dokazi; interpretacija je na istraživaču.</li>
              <li><strong>Vlasnička grupa je kontekst, ne dokaz</strong> — koordinacija unutar iste grupe ima drugačije značenje.</li>
              <li><strong>Degradirani slojevi:</strong> autor (~72% pokrivenosti, varljiv format), tagovi (~53%), broj komentara (~10%) — koriste se samo kao dopunski signali, ne kao zasebne analize.</li>
              <li><strong>AI transparentnost:</strong> svaka klasifikacija nosi confidence; framing i narativi nose citat iz teksta; ose nose obrazloženje — sve je proverljivo i podložno kalibraciji.</li>
              <li><strong>Tišina se meri nad prikupljenim korpusom</strong> — ne nad celokupnom medijskom produkcijom.</li>
            </ul>
          </Section>

          <p className="text-xs text-center pt-2 pb-6" style={{ color: C.muted }}>
            SHARE Fondacija · MediaScope · metodologija usklađena sa implementacijom pipeline-a
          </p>
        </div>
      </div>
    </div>
  )
}
