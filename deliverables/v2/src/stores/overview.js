import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useDataStore } from './data.js'
import { fmt, fmtMoney, pnlClass, pnlSign } from '@/api/client.js'

export const useOverviewStore = defineStore('overview', () => {
  const data = useDataStore()

  const stats = computed(() => {
    let totalAsset = 0, totalCost = 0, totalRealized = 0, totalDiv = 0, totalFees = 0
    for (const [code, p] of Object.entries(data.currentPositions)) {
      const price = data.quotes[code]?.price || 0
      const mv = price * p.qty
      totalAsset += mv; totalCost += p.total_cost
      totalFees += (p.total_commission || 0) + (p.total_stamp_tax || 0) + (p.total_other_fees || 0)
      for (const d of p.dividends || []) totalDiv += d.amount
    }
    for (const [, p] of Object.entries(data.closedPositions)) {
      totalRealized += (p.realized_pnl || 0) + (p.dividends_total || 0)
      totalFees += (p.total_commission || 0) + (p.total_stamp_tax || 0) + (p.total_other_fees || 0)
    }
    const floatPnl = totalAsset - totalCost
    const floatPnlPct = totalCost > 0 ? (floatPnl / totalCost * 100) : 0
    return {
      totalAsset: fmtMoney(totalAsset), totalCost: fmtMoney(totalCost),
      floatPnl: (floatPnl >= 0 ? '+' : '') + fmtMoney(Math.abs(floatPnl)),
      floatPnlPct: (floatPnl >= 0 ? '+' : '') + fmt(floatPnlPct) + '%',
      floatPnlClass: floatPnl >= 0 ? 'profit' : 'loss',
      totalRealized: '+' + fmtMoney(totalRealized + totalDiv),
      totalFees: fmtMoney(totalFees),
    }
  })

  const positionRows = computed(() =>
    Object.entries(data.currentPositions).map(([code, p]) => {
      const q = data.quotes[code] || {}, price = q.price || 0
      const mv = price * p.qty, pnl = mv - p.total_cost
      const pnlPct = p.total_cost > 0 ? (pnl / p.total_cost * 100) : 0
      return {
        code, name: p.name, qty: p.qty.toLocaleString(), avgCost: fmt(p.avg_cost, 3),
        price: fmt(price), priceClass: pnlClass(price - p.avg_cost),
        marketValue: fmtMoney(mv),
        pnl: pnlSign(pnl) + fmtMoney(Math.abs(pnl)),
        pnlPct: pnlSign(pnlPct) + fmt(pnlPct) + '%', pnlClass: pnlClass(pnl),
        dy: q.dy != null ? fmt(q.dy) + '%' : '--',
      }
    })
  )

  const closedRows = computed(() =>
    Object.entries(data.closedPositions).map(([code, p]) => {
      const total = (p.realized_pnl || 0) + (p.dividends_total || 0)
      return {
        code, name: p.name,
        realizedPnl: pnlSign(p.realized_pnl) + fmt(p.realized_pnl),
        realizedClass: pnlClass(p.realized_pnl),
        dividendsTotal: '+' + fmt(p.dividends_total || 0),
        total: pnlSign(total) + fmt(total), totalClass: pnlClass(total),
      }
    })
  )

  const dividendRows = computed(() => {
    const rows = []
    for (const [code, p] of Object.entries(data.currentPositions))
      for (const d of p.dividends || []) rows.push({ date: d.date, name: p.name, perShare: fmt(d.per_share || 0), qty: p.qty, amount: '+' + fmt(d.amount), closed: false })
    for (const [code, p] of Object.entries(data.closedPositions))
      for (const d of p.dividends || []) rows.push({ date: d.date, name: p.name, perShare: fmt(d.per_share || 0), qty: '--', amount: '+' + fmt(d.amount), closed: true })
    return rows
  })

  return { stats, positionRows, closedRows, dividendRows }
})
