export default function MatrixTable({ data, rowKey, colKey, valKey, rowLabel, emptyMsg, getCellUrl }) {
  if (!Array.isArray(data) || data.length === 0) {
    return (
      <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
        {emptyMsg || 'Nema podataka.'}
      </div>
    )
  }

  const rows = [...new Set(data.map(d => d[rowKey]))]
  const cols = [...new Set(data.map(d => d[colKey]))]
  const lookup = {}
  const itemLookup = {}
  for (const d of data) {
    const k = `${d[rowKey]}||${d[colKey]}`
    lookup[k] = d[valKey] || 0
    itemLookup[k] = d
  }
  const maxVal = Math.max(1, ...data.map(d => d[valKey] || 0))

  return (
    <div className="overflow-x-auto">
      <table className="text-xs w-full min-w-max">
        <thead>
          <tr>
            <th className="px-3 py-2 text-left font-medium" style={{ color: 'var(--text-muted)' }}>{rowLabel || 'Izvor'}</th>
            {cols.map(c => (
              <th key={c} className="px-2 py-2 text-center font-medium max-w-[80px]" style={{ color: 'var(--text-muted)' }}>
                <span className="block truncate max-w-[80px]" title={c}>{c}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row} className="border-t" style={{ borderColor: 'var(--border)' }}>
              <td className="px-3 py-1.5 font-mono font-medium whitespace-nowrap" style={{ color: 'var(--text-primary)' }}>{row}</td>
              {cols.map(col => {
                const k = `${row}||${col}`
                const v = lookup[k] || 0
                const item = itemLookup[k]
                const intensity = v / maxVal
                const url = getCellUrl && v > 0 ? getCellUrl(item) : null
                return (
                  <td key={col} className="px-2 py-1.5 text-center tabular-nums"
                    style={{
                      background: v > 0 ? `rgba(99,102,241,${0.1 + intensity * 0.55})` : 'transparent',
                      color: v > 0 ? (intensity > 0.5 ? 'white' : 'var(--text-secondary)') : 'var(--text-muted)',
                      padding: 0,
                    }}>
                    {url ? (
                      <a href={url} target="_blank" rel="noreferrer"
                        className="block w-full h-full px-2 py-1.5 hover:brightness-125"
                        style={{ color: 'inherit', textDecoration: 'none' }}
                        title={`${row} → ${col}: ${v} (klikni za članke)`}>
                        {v}
                      </a>
                    ) : (
                      <span className="block px-2 py-1.5">{v > 0 ? v : '·'}</span>
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
