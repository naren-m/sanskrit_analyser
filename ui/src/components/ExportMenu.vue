<script setup lang="ts">
import { ref } from 'vue'
import { useAnalysisStore } from '../stores/analysis'

const store = useAnalysisStore()

const isOpen = ref(false)

function toggleMenu() {
  isOpen.value = !isOpen.value
}

function closeMenu() {
  isOpen.value = false
}

function exportJSON() {
  if (!store.result) return

  const data = JSON.stringify(store.result, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = `sanskrit-analysis-${store.result.sentence_id}.json`
  link.click()

  URL.revokeObjectURL(url)
  closeMenu()
}

function exportSVG() {
  // Get the Cytoscape SVG from the canvas
  const container = document.querySelector('.cytoscape-container')
  if (!container) {
    console.warn('No Cytoscape container found')
    closeMenu()
    return
  }

  // Create an SVG representation of the parse tree
  const svg = createSVGFromTree()
  const blob = new Blob([svg], { type: 'image/svg+xml' })
  const url = URL.createObjectURL(blob)

  const link = document.createElement('a')
  link.href = url
  link.download = `sanskrit-parse-tree-${store.result?.sentence_id || 'tree'}.svg`
  link.click()

  URL.revokeObjectURL(url)
  closeMenu()
}

function createSVGFromTree(): string {
  const parse = store.currentParse
  if (!parse) return '<svg xmlns="http://www.w3.org/2000/svg"><text>No parse data</text></svg>'

  const nodeWidth = 120
  const nodeHeight = 40
  const levelGap = 80
  const nodeGap = 20

  interface SVGNode {
    id: string
    label: string
    type: string
    x: number
    y: number
    parentId?: string
  }

  const nodes: SVGNode[] = []
  const edges: { from: string; to: string }[] = []

  // Root node
  const rootId = 'sentence'
  nodes.push({
    id: rootId,
    label: store.result?.scripts?.devanagari || 'Sentence',
    type: 'sentence',
    x: 0,
    y: 0,
  })

  // Sandhi groups
  const sgCount = parse.sandhi_groups.length
  parse.sandhi_groups.forEach((sg, sgIdx) => {
    const sgId = `sg_${sgIdx}`
    const sgX = (sgIdx - (sgCount - 1) / 2) * (nodeWidth + nodeGap)
    nodes.push({
      id: sgId,
      label: sg.surface_form,
      type: 'sandhi_group',
      x: sgX,
      y: levelGap,
      parentId: rootId,
    })
    edges.push({ from: rootId, to: sgId })

    // Base words
    const bwCount = sg.base_words.length
    sg.base_words.forEach((bw, bwIdx) => {
      const bwId = `bw_${sgIdx}_${bwIdx}`
      const bwX = sgX + (bwIdx - (bwCount - 1) / 2) * (nodeWidth / 2 + nodeGap / 2)
      nodes.push({
        id: bwId,
        label: bw.lemma,
        type: 'base_word',
        x: bwX,
        y: levelGap * 2,
        parentId: sgId,
      })
      edges.push({ from: sgId, to: bwId })

      // Dhatu
      if (bw.dhatu) {
        const dhatuId = `dhatu_${sgIdx}_${bwIdx}`
        nodes.push({
          id: dhatuId,
          label: `√${bw.dhatu.dhatu}`,
          type: 'dhatu',
          x: bwX,
          y: levelGap * 3,
          parentId: bwId,
        })
        edges.push({ from: bwId, to: dhatuId })
      }
    })
  })

  // Calculate bounds
  const minX = Math.min(...nodes.map((n) => n.x)) - nodeWidth / 2 - 20
  const maxX = Math.max(...nodes.map((n) => n.x)) + nodeWidth / 2 + 20
  const maxY = Math.max(...nodes.map((n) => n.y)) + nodeHeight + 20
  const width = maxX - minX
  const height = maxY + 40
  const offsetX = -minX

  // Color mapping
  const colors: Record<string, { bg: string; border: string }> = {
    sentence: { bg: '#1e40af', border: '#3b82f6' },
    sandhi_group: { bg: '#7c3aed', border: '#a78bfa' },
    base_word: { bg: '#22c55e', border: '#ffffff' },
    dhatu: { bg: '#f97316', border: '#fdba74' },
  }

  // Generate SVG
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">\n`
  svg += `  <style>\n`
  svg += `    text { font-family: 'Noto Sans Devanagari', 'Noto Sans', sans-serif; font-size: 12px; fill: white; }\n`
  svg += `    .title { font-size: 14px; font-weight: bold; }\n`
  svg += `  </style>\n`
  svg += `  <rect width="100%" height="100%" fill="#0f172a"/>\n`

  // Draw edges
  edges.forEach((edge) => {
    const from = nodes.find((n) => n.id === edge.from)
    const to = nodes.find((n) => n.id === edge.to)
    if (from && to) {
      svg += `  <line x1="${from.x + offsetX}" y1="${from.y + nodeHeight / 2 + 10}" x2="${to.x + offsetX}" y2="${to.y + 10}" stroke="#475569" stroke-width="2"/>\n`
    }
  })

  // Draw nodes
  const defaultColor = { bg: '#22c55e', border: '#ffffff' }
  nodes.forEach((node) => {
    const color = colors[node.type] || defaultColor
    const rx = node.type === 'dhatu' ? 20 : 8
    const w = node.type === 'sentence' ? nodeWidth + 20 : nodeWidth
    svg += `  <rect x="${node.x + offsetX - w / 2}" y="${node.y + 10}" width="${w}" height="${nodeHeight}" rx="${rx}" fill="${color.bg}" stroke="${color.border}" stroke-width="2"/>\n`
    svg += `  <text x="${node.x + offsetX}" y="${node.y + nodeHeight / 2 + 15}" text-anchor="middle" class="${node.type === 'sentence' ? 'title' : ''}">${escapeXML(node.label)}</text>\n`
  })

  svg += `</svg>`
  return svg
}

function escapeXML(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}
</script>

<template>
  <div class="export-menu" v-if="store.result">
    <button class="export-btn" @click="toggleMenu">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
      >
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
      Export
    </button>

    <div v-if="isOpen" class="dropdown" @click.self="closeMenu">
      <button class="dropdown-item" @click="exportJSON">
        <span class="icon">{ }</span>
        Export as JSON
      </button>
      <button class="dropdown-item" @click="exportSVG">
        <span class="icon">◇</span>
        Export as SVG
      </button>
    </div>
  </div>
</template>

<style scoped>
.export-menu {
  position: relative;
}

.export-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background-color: var(--border-color);
  color: var(--text-color);
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color 0.2s;
}

.export-btn:hover {
  background-color: #475569;
}

.dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.5rem;
  background-color: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  overflow: hidden;
  z-index: 100;
  min-width: 160px;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem 1rem;
  background: none;
  border: none;
  color: var(--text-color);
  cursor: pointer;
  font-size: 0.875rem;
  text-align: left;
  transition: background-color 0.2s;
}

.dropdown-item:hover {
  background-color: var(--border-color);
}

.dropdown-item .icon {
  width: 1rem;
  text-align: center;
  color: #94a3b8;
}
</style>
