import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { CATEGORY_LABEL } from '../../lib/utils'

const PALETTE = ['#E8A33D', '#4FB4DE', '#8B7FD6', '#5FB88A', '#C4CADA']

export function CategoryChart({ issues }) {
  const counts = {}
  issues.forEach((i) => {
    counts[i.category] = (counts[i.category] || 0) + 1
  })
  const data = Object.entries(counts).map(([key, value]) => ({
    name: CATEGORY_LABEL[key] || key,
    value,
  }))

  if (data.length === 0) return null

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={2}
        >
          {data.map((entry, i) => (
            <Cell key={entry.name} fill={PALETTE[i % PALETTE.length]} stroke="none" />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: '#161C2C',
            border: '1px solid #262E42',
            borderRadius: 8,
            fontSize: 13,
          }}
          labelStyle={{ color: '#EDEFF5' }}
        />
        <Legend
          verticalAlign="bottom"
          height={32}
          formatter={(value) => <span style={{ color: '#8892A6', fontSize: 12 }}>{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
