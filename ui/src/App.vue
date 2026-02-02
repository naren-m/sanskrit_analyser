<script setup lang="ts">
import { ref } from 'vue'
import { useAnalysisStore, type AnalysisMode } from './stores/analysis'
import InputBar from './components/InputBar.vue'
import ParseTree from './components/ParseTree.vue'
import NodeDetail from './components/NodeDetail.vue'
import ExportMenu from './components/ExportMenu.vue'
import { analyzeText, ApiError } from './api/client'

const store = useAnalysisStore()

// Selected tree node for detail view
const selectedNode = ref<{ type: string; data: unknown } | null>(null)

// Handle analyze request from InputBar
async function handleAnalyze(text: string, mode: AnalysisMode) {
  store.setLoading(true)
  store.setError(null)
  selectedNode.value = null

  try {
    const result = await analyzeText(text, mode)
    store.setResult(result)
  } catch (err) {
    if (err instanceof ApiError) {
      store.setError(err.detail || err.message)
    } else if (err instanceof Error) {
      store.setError(err.message)
    } else {
      store.setError('Analysis failed')
    }
  } finally {
    store.setLoading(false)
  }
}

// Handle node selection from ParseTree
function handleNodeSelected(node: { type: string; data: unknown }) {
  selectedNode.value = node
}

// Get display text based on selected script
function getDisplayText(): string {
  if (!store.result?.scripts) return store.result?.original_text || ''
  const scripts = store.result.scripts
  switch (store.displayScript) {
    case 'devanagari':
      return scripts.devanagari || store.result.original_text
    case 'iast':
      return scripts.iast || store.result.original_text
    case 'slp1':
      return scripts.slp1 || store.result.original_text
    default:
      return store.result.original_text
  }
}
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>संस्कृत विश्लेषक</h1>
      <p class="subtitle">Sanskrit Analyzer</p>
    </header>

    <main class="main">
      <!-- Input Section -->
      <InputBar @analyze="handleAnalyze" />

      <!-- Error Display -->
      <div v-if="store.error" class="error-message">
        <span class="error-icon">⚠</span>
        {{ store.error }}
      </div>

      <!-- Results Section -->
      <section v-if="store.result" class="results-section">
        <!-- Result Header -->
        <div class="result-header">
          <div class="result-text">
            <span class="script-label">{{ store.displayScript.toUpperCase() }}:</span>
            <span class="result-value">{{ getDisplayText() }}</span>
          </div>

          <!-- Confidence and Actions -->
          <div class="result-actions">
            <span
              class="confidence-badge"
              :class="{
                high: store.result.confidence.overall >= 0.8,
                medium: store.result.confidence.overall >= 0.5 && store.result.confidence.overall < 0.8,
                low: store.result.confidence.overall < 0.5,
              }"
            >
              {{ (store.result.confidence.overall * 100).toFixed(0) }}% confidence
            </span>
            <span v-if="store.result.needs_human_review" class="review-badge">
              Needs Review
            </span>
            <ExportMenu />
          </div>
        </div>

        <!-- Parse Navigation -->
        <div v-if="store.hasMultipleParses" class="parse-nav">
          <button
            class="nav-btn"
            :disabled="store.currentParseIndex === 0"
            @click="store.previousParse()"
          >
            ← Previous
          </button>
          <span class="parse-indicator">
            Parse {{ store.currentParseIndex + 1 }} of {{ store.parseCount }}
            <span v-if="store.currentParse" class="parse-confidence">
              ({{ (store.currentParse.confidence * 100).toFixed(0) }}%)
            </span>
          </span>
          <button
            class="nav-btn"
            :disabled="store.currentParseIndex === store.parseCount - 1"
            @click="store.nextParse()"
          >
            Next →
          </button>
        </div>

        <!-- Main Content Grid -->
        <div class="content-grid">
          <!-- Parse Tree Visualization -->
          <div class="tree-panel">
            <h3 class="panel-title">Parse Tree</h3>
            <ParseTree @node-selected="handleNodeSelected" />
          </div>

          <!-- Node Detail Panel -->
          <div class="detail-panel">
            <h3 class="panel-title">Node Details</h3>
            <NodeDetail :node="selectedNode" />
          </div>
        </div>

        <!-- Metadata Footer -->
        <div class="result-meta">
          <span><strong>Mode:</strong> {{ store.result.mode }}</span>
          <span><strong>Sentence ID:</strong> {{ store.result.sentence_id }}</span>
          <span v-if="store.result.cache_tier">
            <strong>Cache:</strong> {{ store.result.cache_tier }}
          </span>
        </div>
      </section>

      <!-- Empty State -->
      <section v-else-if="!store.isLoading" class="empty-state">
        <div class="empty-content">
          <h2>Welcome to Sanskrit Analyzer</h2>
          <p>Enter Sanskrit text above to see morphological analysis with:</p>
          <ul>
            <li>3-engine ensemble parsing (Vidyut, Dharmamitra, Heritage)</li>
            <li>Sandhi splitting and lemmatization</li>
            <li>Morphological analysis (case, number, gender, tense)</li>
            <li>Dhātu (verbal root) identification</li>
          </ul>
        </div>
      </section>
    </main>

    <footer class="footer">
      <p>Sanskrit Analyzer v0.1.0 | 3-Engine Ensemble Analysis | Tiered Caching</p>
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
  font-family: 'Noto Sans Devanagari', sans-serif;
}

.subtitle {
  color: #94a3b8;
  margin-top: 0.5rem;
}

.main {
  flex: 1;
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.error-message {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background-color: #7f1d1d;
  border: 1px solid #991b1b;
  color: #fecaca;
  padding: 1rem;
  border-radius: 0.5rem;
}

.error-icon {
  font-size: 1.25rem;
}

.results-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  padding: 1rem 1.5rem;
  background-color: var(--card-bg);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.result-text {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.script-label {
  font-size: 0.75rem;
  color: #64748b;
  font-weight: 500;
}

.result-value {
  font-size: 1.5rem;
  font-family: 'Noto Sans Devanagari', sans-serif;
  color: var(--primary-color);
}

.result-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
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

.review-badge {
  padding: 0.25rem 0.75rem;
  background-color: #7c3aed;
  color: white;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.parse-nav {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1.5rem;
  padding: 0.75rem;
  background-color: var(--card-bg);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.nav-btn {
  padding: 0.5rem 1rem;
  background-color: var(--border-color);
  color: var(--text-color);
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color 0.2s;
}

.nav-btn:hover:not(:disabled) {
  background-color: #475569;
}

.nav-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.parse-indicator {
  color: #94a3b8;
  font-size: 0.875rem;
}

.parse-confidence {
  color: #64748b;
}

.content-grid {
  display: grid;
  grid-template-columns: 1fr 350px;
  gap: 1.5rem;
}

@media (max-width: 1024px) {
  .content-grid {
    grid-template-columns: 1fr;
  }
}

.tree-panel,
.detail-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.panel-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  padding: 0.75rem 1rem;
  background-color: var(--card-bg);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  font-size: 0.8125rem;
  color: #94a3b8;
}

.result-meta strong {
  color: #64748b;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 3rem;
}

.empty-content {
  text-align: center;
  max-width: 500px;
}

.empty-content h2 {
  font-size: 1.5rem;
  color: var(--primary-color);
  margin-bottom: 1rem;
}

.empty-content p {
  color: #94a3b8;
  margin-bottom: 1rem;
}

.empty-content ul {
  text-align: left;
  list-style: none;
  padding: 0;
}

.empty-content li {
  padding: 0.5rem 0;
  padding-left: 1.5rem;
  position: relative;
  color: #94a3b8;
}

.empty-content li::before {
  content: '✓';
  position: absolute;
  left: 0;
  color: var(--primary-color);
}

.footer {
  text-align: center;
  padding: 1rem;
  border-top: 1px solid var(--border-color);
  color: #64748b;
  font-size: 0.875rem;
}
</style>
