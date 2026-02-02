<script setup lang="ts">
import { ref } from 'vue'
import { useAnalysisStore } from './stores/analysis'

const store = useAnalysisStore()

// Selected tree node
const selectedNode = ref<unknown>(null)

// Handle text submission
async function handleAnalyze() {
  if (!store.inputText.trim()) return

  store.setLoading(true)
  store.setError(null)

  try {
    // API call will be implemented in US-030
    console.log('Analyzing:', store.inputText, 'Mode:', store.mode)
    // Mock result for now
    store.setResult({
      sentence_id: 'mock-123',
      original_text: store.inputText,
      normalized_slp1: 'rAmaH gacCati',
      scripts: {
        devanagari: 'रामः गच्छति',
        iast: 'rāmaḥ gacchati',
        slp1: 'rAmaH gacCati',
      },
      parse_forest: [
        {
          parse_id: 'p1',
          confidence: 0.92,
          sandhi_groups: [],
          is_selected: false,
        },
      ],
      confidence: {
        overall: 0.92,
        engine_agreement: 0.90,
      },
      mode: store.mode,
      needs_human_review: false,
    })
  } catch (err) {
    store.setError(err instanceof Error ? err.message : 'Analysis failed')
  } finally {
    store.setLoading(false)
  }
}

// Handle node selection in tree (will be used by ParseTree component)
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function handleNodeSelected(node: unknown) {
  selectedNode.value = node
}

// Export for future use
defineExpose({ handleNodeSelected })
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>संस्कृत विश्लेषक</h1>
      <p class="subtitle">Sanskrit Analyzer</p>
    </header>

    <main class="main">
      <!-- Input Section -->
      <section class="input-section">
        <div class="input-controls">
          <input
            v-model="store.inputText"
            type="text"
            class="text-input"
            placeholder="संस्कृत वाक्यं लिखतु... (Enter Sanskrit text)"
            @keyup.enter="handleAnalyze"
          />

          <select v-model="store.mode" class="mode-select">
            <option value="production">Production</option>
            <option value="educational">Educational</option>
            <option value="academic">Academic</option>
          </select>

          <select v-model="store.displayScript" class="script-select">
            <option value="devanagari">देवनागरी</option>
            <option value="iast">IAST</option>
            <option value="slp1">SLP1</option>
          </select>

          <button
            class="analyze-btn"
            :disabled="store.isLoading || !store.inputText.trim()"
            @click="handleAnalyze"
          >
            {{ store.isLoading ? 'विश्लेषणम्...' : 'विश्लेषयतु (Analyze)' }}
          </button>
        </div>
      </section>

      <!-- Error Display -->
      <div v-if="store.error" class="error-message">
        {{ store.error }}
      </div>

      <!-- Results Section -->
      <section v-if="store.result" class="results-section">
        <!-- Parse Navigation -->
        <div v-if="store.hasMultipleParses" class="parse-nav">
          <button
            :disabled="store.currentParseIndex === 0"
            @click="store.previousParse()"
          >
            ← Previous
          </button>
          <span class="parse-indicator">
            Parse {{ store.currentParseIndex + 1 }} of {{ store.parseCount }}
          </span>
          <button
            :disabled="store.currentParseIndex === store.parseCount - 1"
            @click="store.nextParse()"
          >
            Next →
          </button>
        </div>

        <!-- Confidence Display -->
        <div class="confidence-display">
          <span
            class="confidence-badge"
            :class="{
              high: store.result.confidence.overall >= 0.8,
              medium: store.result.confidence.overall >= 0.5 && store.result.confidence.overall < 0.8,
              low: store.result.confidence.overall < 0.5,
            }"
          >
            Confidence: {{ (store.result.confidence.overall * 100).toFixed(0) }}%
          </span>
        </div>

        <!-- Tree Visualization Placeholder -->
        <div class="tree-container">
          <p class="placeholder-text">
            Parse tree visualization will be rendered here (Cytoscape)
          </p>
          <div class="tree-info">
            <p><strong>Original:</strong> {{ store.result.original_text }}</p>
            <p><strong>Normalized:</strong> {{ store.result.normalized_slp1 }}</p>
            <p><strong>Mode:</strong> {{ store.result.mode }}</p>
          </div>
        </div>

        <!-- Node Detail Placeholder -->
        <div v-if="selectedNode" class="node-detail">
          <h3>Selected Node Details</h3>
          <pre>{{ JSON.stringify(selectedNode, null, 2) }}</pre>
        </div>
      </section>
    </main>

    <footer class="footer">
      <p>Sanskrit Analyzer v0.1.0 | 3-Engine Ensemble Analysis</p>
    </footer>
  </div>
</template>

<style>
:root {
  --primary-color: #f97316;
  --bg-color: #0f172a;
  --card-bg: #1e293b;
  --text-color: #e2e8f0;
  --border-color: #334155;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Noto Sans', 'Noto Sans Devanagari', sans-serif;
  background-color: var(--bg-color);
  color: var(--text-color);
}

.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  text-align: center;
  padding: 2rem;
  border-bottom: 1px solid var(--border-color);
}

.header h1 {
  font-size: 2.5rem;
  color: var(--primary-color);
}

.subtitle {
  color: #94a3b8;
  margin-top: 0.5rem;
}

.main {
  flex: 1;
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.input-section {
  margin-bottom: 2rem;
}

.input-controls {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.text-input {
  flex: 1;
  min-width: 300px;
  padding: 0.75rem 1rem;
  font-size: 1.1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background-color: var(--card-bg);
  color: var(--text-color);
}

.text-input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.mode-select,
.script-select {
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background-color: var(--card-bg);
  color: var(--text-color);
  cursor: pointer;
}

.analyze-btn {
  padding: 0.75rem 1.5rem;
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: 0.5rem;
  font-size: 1rem;
  cursor: pointer;
  transition: background-color 0.2s;
}

.analyze-btn:hover:not(:disabled) {
  background-color: #ea580c;
}

.analyze-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.error-message {
  background-color: #7f1d1d;
  border: 1px solid #991b1b;
  color: #fecaca;
  padding: 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.results-section {
  background-color: var(--card-bg);
  border-radius: 0.5rem;
  padding: 1.5rem;
  border: 1px solid var(--border-color);
}

.parse-nav {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.parse-nav button {
  padding: 0.5rem 1rem;
  background-color: var(--border-color);
  color: var(--text-color);
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
}

.parse-nav button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.parse-indicator {
  color: #94a3b8;
}

.confidence-display {
  text-align: center;
  margin-bottom: 1rem;
}

.confidence-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.875rem;
  font-weight: 500;
}

.confidence-badge.high {
  background-color: #166534;
  color: #dcfce7;
}

.confidence-badge.medium {
  background-color: #854d0e;
  color: #fef9c3;
}

.confidence-badge.low {
  background-color: #991b1b;
  color: #fecaca;
}

.tree-container {
  background-color: var(--bg-color);
  border-radius: 0.5rem;
  padding: 2rem;
  min-height: 300px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.placeholder-text {
  color: #64748b;
  font-style: italic;
  margin-bottom: 1rem;
}

.tree-info {
  text-align: left;
  width: 100%;
  max-width: 500px;
}

.tree-info p {
  margin: 0.5rem 0;
}

.node-detail {
  margin-top: 1rem;
  padding: 1rem;
  background-color: var(--bg-color);
  border-radius: 0.5rem;
}

.node-detail pre {
  overflow-x: auto;
  font-size: 0.875rem;
}

.footer {
  text-align: center;
  padding: 1rem;
  border-top: 1px solid var(--border-color);
  color: #64748b;
  font-size: 0.875rem;
}
</style>
