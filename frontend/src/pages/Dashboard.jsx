import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Newspaper, Radio, TrendingUp, Sun } from 'lucide-react'
import { useFilters, toParams } from '../store/filters'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'

const INTRADAY_COLORS = ['#6366f1', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

function IntradayCard({ filterParams }) {
  const { data } = useQuery({
    queryKey: ['intraday', filterParams],
    queryFn: () => api.get(`/intraday?${filterParams}`).then(r => r.data),
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
    queryFn: () => api.get('/summary/history?limit=30').then(r => r.data.summaries),
    retry: false,
  })

  if (isLoading || !data?.narrative) return null
  const n = data.narrative
  const summaries = history || []

  return (
    <div className="rounded-xl border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
      <div className="px-4 py-3 border-b flex items-center gap-2" style={{ borderColor: 'var(--border)' }}>
        <Sun size={14} style={{ color: '#f59e0b' }} />
        <h2 className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
          Dnevni pregled — {data.date}
        </h2>
        {summaries.length > 1 && (
          <select value={selectedDate || ''} onChange={e => setSelectedDate(e.target.value || null)}
            className="ml-auto text-xs px-2 py-1 rounded border outline-none"
            style={{ background: 'var(--bg-elevated)', borderColor: 'var(--border)', color: 'var(--text-secondary)' }}>
            <option value="">Najnoviji</option>
            {summaries.map(s => (
              <option key={s.date} value={s.date}>{s.date}{s.headline ? ` — ${s.headline.slice(0, 40)}` : ''}</option>
            ))}
          </select>
        )}
        {summaries.length <= 1 && <span className="text-xs ml-auto" style={{ color: 'var(--text-muted)' }}>AI generisano</span>}
      </div>
      <div className="p-4 space-y-3">
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
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Dashboard</h1>
        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>Pregled medijskog pejzaža — srpski portali</p>
      </div>

      <MorningSummary />

      {/* Stat kartice */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard icon={Newspaper} label="Ukupno članaka" value={stats?.total?.toLocaleString()} sub="u bazi" />
        <StatCard
          icon={TrendingUp} label="Analizirano"
          value={stats?.analyzed?.toLocaleString()}
          sub={`${stats?.pipeline_pct ?? 0}% od ukupnog`}
          accent={stats?.pipeline_pct === 100 ? '#22c55e' : '#f59e0b'}
        />
        <StatCard icon={Radio} label="Aktivnih izvora" value={stats?.active_sources} sub="srpskih medija" />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Top teme */}
        <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-sm font-medium mb-4" style={{ color: 'var(--text-primary)' }}>
            Distribucija tema
            {data?.stats?.analyzed ? <span className="ml-2 text-xs font-normal" style={{ color: 'var(--text-muted)' }}>({data.stats.analyzed.toLocaleString()} čl.)</span> : null}
          </h2>
          {topTopics.length > 0 ? (
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={topTopics} layout="vertical" margin={{ left: 0, right: 16 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="topic" width={100}
                  tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: 'var(--text-primary)' }}
                />
                <Bar dataKey="count" radius={3}>
                  {topTopics.map((_, i) => <Cell key={i} fill={`hsl(${220 + i * 15}, 60%, 55%)`} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-52 flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
              {isLoading ? 'Učitavanje...' : 'Pipeline analiza u toku...'}
            </div>
          )}
        </div>

        {/* Desna kolona: political + sentiment */}
        <div className="space-y-4">
          {/* Political score po izvoru */}
          <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
            <h2 className="text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Prosečan politički skor</h2>
            <div className="flex justify-between text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
              <span>← Opoziciono</span>
              <span>Pro-vladino →</span>
            </div>
            {sourceScores.length > 0 ? (
              <div className="space-y-0.5 max-h-48 overflow-y-auto">
                {sourceScores.map(s => (
                  <PoliticalBar key={s.source_id} source={s.name} score={s.avg_score} count={s.count} />
                ))}
              </div>
            ) : (
              <div className="h-32 flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
                {isLoading ? 'Učitavanje...' : 'Pipeline analiza u toku...'}
              </div>
            )}
          </div>

          {/* Sentiment breakdown */}
          {sentimentTotal > 0 && (
            <div className="rounded-xl p-4 border" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
              <h2 className="text-sm font-medium mb-3" style={{ color: 'var(--text-primary)' }}>Sentiment</h2>
              <div className="flex gap-1 h-3 rounded-full overflow-hidden mb-3">
                {Object.entries(sentiment).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                  <div key={s} style={{ width: `${n / sentimentTotal * 100}%`, background: SENTIMENT_COLORS[s] }} />
                ))}
              </div>
              <div className="flex flex-wrap gap-3">
                {Object.entries(sentiment).sort((a, b) => b[1] - a[1]).map(([s, n]) => (
                  <div key={s} className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: SENTIMENT_COLORS[s] }} />
                    <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {SENTIMENT_LABELS[s] || s}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {Math.round(n / sentimentTotal * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <IntradayCard filterParams={filterParams} />

      {/* Poslednji analizirani clanci */}
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
