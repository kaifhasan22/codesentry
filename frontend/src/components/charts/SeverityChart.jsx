import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { SEVERITY_ORDER, SEVERITY_LABEL } from '../../lib/utils'

const COLORS = {
  critical: '#E5484D',
  high: '#F2994A',
  medium: '#EAC54F',
  low: '#4FB4DE',
  info: '#8892A6',
}

export function SeverityChart({ issues }) {
  const data = SEVERITY_ORDER.map((sev) => ({
    key: sev,
    name: SEVERITY_LABEL[sev],
    count: issues.filter((i) => i.severity === sev).length,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
        <XAxis
          dataKey="name"
          tick={{ fill: '#8892A6', fontSize: 12 }}
          axisLine={{ stroke: '#262E42' }}
          tickLine={false}
        />
        <YAxis
          allowDecimals={false}
          tick={{ fill: '#8892A6', fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          contentStyle={{
            background: '#161C2C',
            border: '1px solid #262E42',
            borderRadius: 8,
            fontSize: 13,
          }}
          labelStyle={{ color: '#EDEFF5' }}
        />
        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell key={entry.key} fill={COLORS[entry.key]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
