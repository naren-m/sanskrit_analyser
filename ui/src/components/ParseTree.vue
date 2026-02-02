<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import cytoscape, { type Core, type NodeSingular } from 'cytoscape'
import { useAnalysisStore, type ParseTree, type SandhiGroup, type BaseWord } from '../stores/analysis'

const store = useAnalysisStore()

const emit = defineEmits<{
  'node-selected': [node: { type: string; data: SandhiGroup | BaseWord | unknown }]
}>()

const containerRef = ref<HTMLElement | null>(null)
let cy: Core | null = null

// Get confidence color
function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return '#22c55e' // green
  if (confidence >= 0.5) return '#eab308' // yellow
  return '#ef4444' // red
}

// Build Cytoscape elements from parse tree
function buildElements(parse: ParseTree) {
  const elements: cytoscape.ElementDefinition[] = []

  // Root node (sentence)
  const rootId = 'sentence'
  elements.push({
    data: {
      id: rootId,
      label: store.result?.scripts?.devanagari || store.result?.original_text || 'Sentence',
      type: 'sentence',
      confidence: parse.confidence,
    },
  })

  // Sandhi groups
  parse.sandhi_groups.forEach((sg, sgIndex) => {
    const sgId = `sg_${sgIndex}`

    elements.push({
      data: {
        id: sgId,
        label: sg.surface_form,
        type: 'sandhi_group',
        confidence: 1.0,
        groupData: sg,
      },
    })

    // Edge from root to sandhi group
    elements.push({
      data: {
        id: `edge_${rootId}_${sgId}`,
        source: rootId,
        target: sgId,
      },
    })

    // Base words
    sg.base_words.forEach((bw, bwIndex) => {
      const bwId = `bw_${sgIndex}_${bwIndex}`

      elements.push({
        data: {
          id: bwId,
          label: bw.lemma,
          type: 'base_word',
          confidence: bw.confidence,
          wordData: bw,
        },
      })

      // Edge from sandhi group to base word
      elements.push({
        data: {
          id: `edge_${sgId}_${bwId}`,
          source: sgId,
          target: bwId,
        },
      })

      // Dhatu node if present
      if (bw.dhatu) {
        const dhatuId = `dhatu_${sgIndex}_${bwIndex}`

        elements.push({
          data: {
            id: dhatuId,
            label: `√${bw.dhatu.dhatu}`,
            type: 'dhatu',
            confidence: 1.0,
            dhatuData: bw.dhatu,
          },
        })

        elements.push({
          data: {
            id: `edge_${bwId}_${dhatuId}`,
            source: bwId,
            target: dhatuId,
          },
        })
      }
    })
  })

  return elements
}

// Initialize Cytoscape
function initCytoscape() {
  if (!containerRef.value) return

  cy = cytoscape({
    container: containerRef.value,
    elements: [],
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': '14px',
          'font-family': 'Noto Sans Devanagari, Noto Sans, sans-serif',
          'color': '#e2e8f0',
          'text-outline-color': '#1e293b',
          'text-outline-width': 2,
          'width': 80,
          'height': 40,
          'shape': 'roundrectangle',
          'background-color': '#334155',
          'border-width': 2,
          'border-color': '#475569',
        },
      },
      {
        selector: 'node[type="sentence"]',
        style: {
          'background-color': '#1e40af',
          'border-color': '#3b82f6',
          'width': 120,
          'height': 50,
          'font-size': '16px',
          'font-weight': 'bold',
        },
      },
      {
        selector: 'node[type="sandhi_group"]',
        style: {
          'background-color': '#7c3aed',
          'border-color': '#a78bfa',
        },
      },
      {
        selector: 'node[type="base_word"]',
        style: {
          'background-color': (ele: NodeSingular) => getConfidenceColor(ele.data('confidence')),
          'border-color': '#ffffff',
          'border-width': 3,
        },
      },
      {
        selector: 'node[type="dhatu"]',
        style: {
          'background-color': '#f97316',
          'border-color': '#fdba74',
          'shape': 'ellipse',
          'width': 70,
          'height': 35,
        },
      },
      {
        selector: 'node:selected',
        style: {
          'border-width': 4,
          'border-color': '#ffffff',
        },
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#475569',
          'target-arrow-color': '#475569',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
        },
      },
    ],
    layout: {
      name: 'breadthfirst',
      directed: true,
      spacingFactor: 1.5,
      padding: 50,
      avoidOverlap: true,
    },
    wheelSensitivity: 0.3,
    minZoom: 0.3,
    maxZoom: 3,
  })

  // Handle node clicks
  cy.on('tap', 'node', (event) => {
    const node = event.target
    const nodeType = node.data('type')

    let data: unknown = null
    if (nodeType === 'sandhi_group') {
      data = node.data('groupData')
    } else if (nodeType === 'base_word') {
      data = node.data('wordData')
    } else if (nodeType === 'dhatu') {
      data = node.data('dhatuData')
    }

    emit('node-selected', { type: nodeType, data })
  })

  // Fit to viewport
  cy.fit(undefined, 50)
}

// Update graph when parse changes
function updateGraph() {
  if (!cy || !store.currentParse) return

  const elements = buildElements(store.currentParse)
  cy.elements().remove()
  cy.add(elements)

  cy.layout({
    name: 'breadthfirst',
    directed: true,
    spacingFactor: 1.5,
    padding: 50,
    avoidOverlap: true,
  }).run()

  cy.fit(undefined, 50)
}

// Watch for parse changes
watch(() => store.currentParse, () => {
  updateGraph()
}, { deep: true })

watch(() => store.currentParseIndex, () => {
  updateGraph()
})

onMounted(() => {
  initCytoscape()
  if (store.currentParse) {
    updateGraph()
  }
})

onUnmounted(() => {
  if (cy) {
    cy.destroy()
    cy = null
  }
})

// Helper methods for controls
function fitView() {
  cy?.fit(undefined, 50)
}

function centerView() {
  cy?.center()
}

// Expose methods for parent
defineExpose({
  fit: fitView,
  center: centerView,
  reset: () => cy?.reset(),
})
</script>

<template>
  <div class="parse-tree-container">
    <div ref="containerRef" class="cytoscape-container"></div>

    <div v-if="!store.currentParse" class="empty-state">
      <p>Enter Sanskrit text and click Analyze to see the parse tree</p>
    </div>

    <div class="controls">
      <button @click="fitView" title="Fit to view">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
        </svg>
      </button>
      <button @click="centerView" title="Center">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/>
          <circle cx="12" cy="12" r="3"/>
        </svg>
      </button>
    </div>

    <div class="legend">
      <div class="legend-item">
        <span class="legend-color" style="background: #1e40af"></span>
        <span>Sentence</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #7c3aed"></span>
        <span>Sandhi Group</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #22c55e"></span>
        <span>Word (High)</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #eab308"></span>
        <span>Word (Med)</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #ef4444"></span>
        <span>Word (Low)</span>
      </div>
      <div class="legend-item">
        <span class="legend-color" style="background: #f97316; border-radius: 50%"></span>
        <span>Dhatu</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.parse-tree-container {
  position: relative;
  background-color: var(--bg-color);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.cytoscape-container {
  width: 100%;
  height: 400px;
}

.empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #64748b;
  font-style: italic;
}

.controls {
  position: absolute;
  top: 1rem;
  right: 1rem;
  display: flex;
  gap: 0.5rem;
}

.controls button {
  padding: 0.5rem;
  background-color: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  color: var(--text-color);
  cursor: pointer;
  transition: background-color 0.2s;
}

.controls button:hover {
  background-color: var(--border-color);
}

.legend {
  position: absolute;
  bottom: 1rem;
  left: 1rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  background-color: rgba(30, 41, 59, 0.9);
  border-radius: 0.375rem;
  font-size: 0.75rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.legend-color {
  width: 12px;
  height: 12px;
  border-radius: 2px;
}
</style>
