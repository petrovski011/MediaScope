import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from 'recharts'
import { Newspaper, Radio, TrendingUp, Sun, AlertTriangle } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'

const INTRADAY_COLORS = ['#6366f1', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

function IntradayCard({ filterParams }) {
  const { data } = useQuery({
    queryKey: ['intraday', filterParams],
    queryFn: () => api.get(`/intraday?${new URLSearchParams(filterParams)}`).then(r => r.data),
  })
  if (!data?.hourly) return null
  const topics = data.topics || []
  const hasData = data.hourly.some(h => topics.some(t => h[t]))
  if (!hasData) return null

  return (
    <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <h2 className="text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Intra-day distribucija (po satu)</h2>
      <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
        {data.intraday_note?.excluded_sources?.length
          ? `Bez ${data.intraday_note.excluded_sources.join(', ')} — ${data.intraday_note.reason}`
          : 'Samo članci sa poznatim tačnim vremenom objave'
        }
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data.hourly} margin={{ left: 0, right: 8 }}>
          <XAxis dataKey="hour" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
          <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={28} />
          <Tooltip contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
          {topics.map((t, i) => (
            <Bar key={t} dataKey={t} stackId="a" fill={INTRADAY_COLORS[i % INTRADAY_COLORS.length]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function MorningSummary() {
  const [selectedDate, setSelectedDate] = useState(null)
  const { data, isLoading } = useQuery({
    queryKey: ['morning-summary', selectedDate],
    queryFn: () => api.get(`/summary${selectedDate ? `?target_date=${selectedDate}` : ''}`).then(r => r.data),
    staleTime: 30 * 60 * 1000,
    retry: false,
  })
  const { data: history } = useQuery({
    queryKey: ['summary-history'],
    queryFn: () => api.get('/summary/history?limit=90').then(r => r.data.summaries),
    retry: false,
  })

  const summaries = history || []
  const availableDates = new Set(summaries.map(s => s.date))
  const minDate = summaries.length ? summaries[summaries.length - 1].date : undefined
  const maxDate = summaries.length ? summaries[0].date : undefined

  if (isLoading && !selectedDate) return null
  if (!isLoading && !data?.narrative && !selectedDate) return null

  const n = data?.narrative

  return (
    <div className="rounded-xl border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center gap-2 flex-wrap" style={{ borderColor: 'var(--border)' }}>
        <Sun size={14} style={{ color: '#f59e0b' }} />
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Dnevni pregled{data?.date ? ` — ${data.date}` : ''}
        </h2>
        <div className="ml-auto flex items-center gap-2">
          {selectedDate && (
            <button onClick={() => setSelectedDate(null)}
              className="text-xs px-2 py-1 rounded border transition-colors"
              style={{ borderColor: 'var(--border)', color: 'var(--accent)', background: 'var(--bg-elevated)' }}>
              Najnoviji
            </button>
          )}
          {summaries.length > 0 && (
            <input type="date"
              value={selectedDate || ''}
              min={minDate} max={maxDate}
              onChange={e => setSelectedDate(e.target.value || null)}
              className="text-xs px-2 py-1 rounded border outline-none"
              style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-secondary)' }} />
          )}
          {summaries.length === 0 && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>AI generisano</span>}
        </div>
      </div>
      <div className="p-4 space-y-3">
        {isLoading ? (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Učitavanje…</p>
        ) : !n ? (
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Nema sačuvanog pregleda za {selectedDate}. Pregledi se generišu automatski svako jutro u 07:00.
          </p>
        ) : (
          <>
            {n.headline && (
              <div className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{n.headline}</div>
            )}
            {n.overview && (
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{n.overview}</p>
            )}
            {n.key_themes?.length > 0 && (
              <div>
                <div className="text-xs font-medium mb-2" style={{ color: 'var(--text-muted)' }}>Ključne teme</div>
                <ul className="space-y-1">
                  {n.key_themes.map((t, i) => (
                    <li key={i} className="text-sm flex items-start gap-2">
                      <span className="mt-1.5 w-1 h-1 rounded-full shrink-0" style={{ background: 'var(--text-muted)' }} />
                      <span style={{ color: 'var(--text-secondary)' }}>{t}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {n.coordination_note && (
              <div className="rounded-lg p-3 text-xs" style={{ background: 'rgba(245,158,11,0.08)', color: '#fbbf24' }}>
                ⚠ {n.coordination_note}
              </div>
            )}
            {n.editorial_note && (
              <div className="text-xs pt-2 border-t" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
                Napomena: {n.editorial_note}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, sub, accent }) {
  return (
    <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-2 mb-3">
        <Icon size={14} style={{ color: accent || 'var(--text-muted)' }} />
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</span>
      </div>
      <div className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>{value ?? '—'}</div>
      {sub && <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>{sub}</div>}
    </div>
  )
}

function PoliticalBar({ score, source, count }) {
  const pct = ((score + 1) / 2) * 100
  const color = score > 0.3 ? '#ef4444' : score < -0.3 ? '#3b82f6' : '#6b7280'
  return (
    <div className="flex items-center gap-3 py-1.5">
      <div className="w-24 text-xs shrink-0 truncate" style={{ color: 'var(--text-secondary)' }}>{source}</div>
      <div className="flex-1 h-1.5 rounded-full" style={{ background: 'var(--bg-elevated)' }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="w-10 text-xs text-right tabular-nums" style={{ color: 'var(--text-muted)' }}>
        {score > 0 ? '+' : ''}{score.toFixed(2)}
      </div>
    </div>
  )
}

const TOPIC_LABELS = {
  POLITIKA: 'Politika', EU_INTEGRACIJE: 'EU', KOSOVO: 'Kosovo',
  EKONOMIJA: 'Ekonomija', INFRASTRUKTURA: 'Infrastruktura', BEZBEDNOST: 'Bezbednost',
  MEDIJSKE_SLOBODE: 'Med. slobode', MEDIJI_SLOBODA: 'Med. slobode',
  PROTEST: 'Protest', KULTURA: 'Kultura', ZABAVA_I_ESTRADA: 'Zabava', SPORT: 'Sport',
  HRONIKA: 'Hronika', ZDRAVLJE: 'Zdravlje', OBRAZOVANJE: 'Obrazovanje',
  SPOLJNA_POLITIKA: 'Spoljna pol.', LOKALNA_VLAST: 'Lokalna vlast', DRUSTVO: 'Društvo',
}

const SENTIMENT_COLORS = { positive: '#22c55e', negative: '#ef4444', neutral: '#6b7280', mixed: '#f59e0b' }
const SENTIMENT_LABELS = { positive: 'Pozitivan', negative: 'Negativan', neutral: 'Neutralan', mixed: 'Mešovit' }

const ANOMALY_LABELS = { topic_surge: 'Skok teme', topic_silence: 'Tišina', framing_shift: 'Framing shift', anomaly: 'Anomalija' }

function AnomaliesCard() {
  const navigate = useNavigate()
  const { data: anomData } = useQuery({
    queryKey: ['dashboard-anomalies'],
    queryFn: () => api.get('/anomalies?limit=6').then(r => r.data),
  })
  const anomalies = anomData?.anomalies || []
  const fmtDate = (s) => {
    if (!s) return ''
    const d = new Date(s)
    return d.toLocaleDateString('sr-RS', { day: '2-digit', month: '2-digit' })
  }
  return (
    <div className="rounded-xl border flex flex-col" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-2.5 border-b flex items-center gap-2 shrink-0" style={{ borderColor: 'var(--border)' }}>
        <AlertTriangle size={13} style={{ color: '#f59e0b' }} />
        <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Anomalije</span>
        <button onClick={() => navigate('/anomalies')}
          className="ml-auto text-xs hover:underline" style={{ color: 'var(--accent)' }}>sve →</button>
      </div>
      {anomalies.length > 0 ? (
        <div className="divide-y flex-1" style={{ borderColor: 'var(--border)' }}>
          {anomalies.map(a => (
            <div key={a.id} className="px-4 py-2.5 flex items-center gap-2">
              <span className="text-[10px] px-1.5 py-0.5 rounded shrink-0"
                style={{ background: '#f59e0b22', color: '#f59e0b' }}>
                {ANOMALY_LABELS[a.anomaly_type] || a.anomaly_type}
              </span>
              <span className="text-xs flex-1 truncate" style={{ color: 'var(--text-secondary)' }}>
                {a.topic || a.framing_name || a.narrative_name || '—'}
              </span>
              <span className="text-xs shrink-0 tabular-nums" style={{ color: 'var(--text-muted)' }}>{fmtDate(a.detected_at)}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
          Nema novih anomalija
        </div>
      )}
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { dateFrom, dateTo, selectedSources } = useFilters()
  const filterParams = toParams({ dateFrom, dateTo, selectedSources })

  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', dateFrom, dateTo, selectedSources.join(',')],
    queryFn: () => {
      const p = new URLSearchParams(filterParams)
      return api.get(`/dashboard?${p}`).then(r => r.data)
    },
  })

  const stats = data?.stats
  const topTopics = data?.topics?.slice(0, 8).map(t => ({
    topic: TOPIC_LABELS[t.topic] || t.topic,
    count: t.count,
  })) || []
  const sourceScores = data?.political_by_source || []
  const sentiment = data?.sentiment || {}
  const sentimentTotal = Object.values(sentiment).reduce((a, b) => a + b, 0)

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Dashboard</h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>Pregled medijskog pejzaža — srpski portali</p>
      </div>

      <MorningSummary />

      {/* ROW 1: Stat kartice stacked | Pie chart | Anomalije */}
      <div className="grid grid-cols-3 gap-4" style={{ alignItems: 'stretch' }}>
        {/* Col 1 — 3 stat kartice stacked */}
        <div className="flex flex-col gap-3">
          <StatCard icon={Newspaper} label="Ukupno članaka" value={stats?.total?.toLocaleString()} sub="u bazi" />
          <StatCard
            icon={TrendingUp} label="Analizirano"
            value={stats?.analyzed?.toLocaleString()}
            sub={`${stats?.pipeline_pct ?? 0}% od ukupnog`}
            accent={stats?.pipeline_pct === 100 ? '#22c55e' : '#f59e0b'}
          />
          <StatCard icon={Radio} label="Aktivnih izvora" value={stats?.active_sources} sub="srpskih medija" />
        </div>

        {/* Col 2 — Distribucija tema (pie) */}
        <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
            Distribucija tema
            {data?.stats?.analyzed ? <span className="ml-2 text-xs font-normal" style={{ color: 'var(--text-muted)' }}>({data.stats.analyzed.toLocaleString()} čl.)</span> : null}
          </h2>
          {topTopics.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={topTopics} dataKey="count" nameKey="topic" cx="50%" cy="45%"
                  outerRadius={82} paddingAngle={2}
                  label={({ topic, percent }) => percent > 0.05 ? `${topic.split(' ')[0]} ${Math.round(percent * 100)}%` : ''}
                  labelLine={false}>
                  {topTopics.map((_, i) => <Cell key={i} fill={`hsl(${220 + i * 18}, 55%, 55%)`} />)}
                </Pie>
                <Tooltip
                  contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                  formatter={(v, name) => [v, name]}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-52 flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
              {isLoading ? 'Učitavanje...' : 'Pipeline analiza u toku...'}
            </div>
          )}
        </div>

        {/* Col 3 — Anomalije */}
        <AnomaliesCard />
      </div>

      {/* ROW 2: Politički skor — puna širina, landscape */}
      <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Prosečan politički skor</h2>
          <div className="flex gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
            <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{ background: '#3b82f6' }} />Opoziciono</span>
            <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{ background: '#6b7280' }} />Neutralno</span>
            <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full" style={{ background: '#ef4444' }} />Pro-vladino</span>
          </div>
        </div>
        {sourceScores.length > 0 ? (
          <div className="grid gap-x-6 gap-y-0" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
            {sourceScores.map(s => (
              <PoliticalBar key={s.source_id} source={s.name} score={s.avg_score} count={s.count} />
            ))}
          </div>
        ) : (
          <div className="h-16 flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
            {isLoading ? 'Učitavanje...' : 'Pipeline analiza u toku...'}
          </div>
        )}
      </div>

      {/* ROW 3: Sentiment — landscape, tanak */}
      {sentimentTotal > 0 && (
        <div className="rounded-xl border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <div className="px-4 py-2.5 border-b flex items-center gap-3" style={{ borderColor: 'var(--border)' }}>
            <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Sentiment</h2>
            <span className="text-xs italic" style={{ color: 'var(--text-muted)' }}>klik → filtrirani članci</span>
          </div>
          <div className="px-4 py-3 flex items-center gap-4">
            {/* Stacked bar */}
            <div className="flex h-3 rounded-full overflow-hidden flex-1 gap-px">
              {Object.entries(sentiment).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                <button key={s}
                  onClick={() => navigate(`/articles?sentiment=${s}`)}
                  title={`${SENTIMENT_LABELS[s] || s}: ${n} čl.`}
                  style={{ width: `${n / sentimentTotal * 100}%`, background: SENTIMENT_COLORS[s] }}
                  className="hover:brightness-125 transition-all" />
              ))}
            </div>
            {/* Legend + counts */}
            <div className="flex items-center gap-5 shrink-0">
              {Object.entries(sentiment).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                <button key={s} onClick={() => navigate(`/articles?sentiment=${s}`)}
                  className="flex items-center gap-1.5 hover:opacity-80 transition-opacity">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: SENTIMENT_COLORS[s] }} />
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{SENTIMENT_LABELS[s] || s}</span>
                  <span className="text-xs tabular-nums font-medium" style={{ color: 'var(--text-primary)' }}>{n.toLocaleString()}</span>
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>({Math.round(n / sentimentTotal * 100)}%)</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ROW 4: Intraday */}
      <IntradayCard filterParams={filterParams} />

      {/* ROW 5: Poslednji analizirani clanci */}
      <div className="rounded-xl border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Poslednji analizirani članci</h2>
        </div>
        <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
          {data?.recent_articles?.map(a => (
            <div key={a.id} onClick={() => navigate(`/articles/${a.id}`)}
              className="px-4 py-3 flex items-start gap-3 cursor-pointer hover:bg-white/[0.02] transition-colors">
              <span className="text-xs px-2 py-0.5 rounded shrink-0 mt-0.5"
                style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>
                {a.source_id}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>{a.title}</div>
                <div className="flex items-center gap-3 mt-1">
                  {a.primary_topic && (
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {TOPIC_LABELS[a.primary_topic] || a.primary_topic}
                    </span>
                  )}
                  {a.sentiment && (
                    <span className="text-xs" style={{ color: SENTIMENT_COLORS[a.sentiment] }}>
                      {SENTIMENT_LABELS[a.sentiment] || a.sentiment}
                    </span>
                  )}
                </div>
              </div>
              {a.political_score != null && (
                <div className="text-xs shrink-0 tabular-nums" style={{
                  color: a.political_score > 0.3 ? '#ef4444' : a.political_score < -0.3 ? '#3b82f6' : '#6b7280'
                }}>
                  {a.political_score > 0 ? '+' : ''}{a.political_score.toFixed(2)}
                </div>
              )}
            </div>
          ))}
          {(!data?.recent_articles?.length) && (
            <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              {isLoading ? 'Učitavanje...' : 'Pipeline analiza u toku — podaci će biti dostupni uskoro'}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
