<script setup lang="ts">
import { computed } from 'vue'
import type { SandhiGroup, BaseWord, DhatuInfo } from '../stores/analysis'

interface NodeData {
  type: string
  data: SandhiGroup | BaseWord | DhatuInfo | unknown
}

const props = defineProps<{
  node: NodeData | null
}>()

const isSandhiGroup = computed(() => props.node?.type === 'sandhi_group')
const isBaseWord = computed(() => props.node?.type === 'base_word')
const isDhatu = computed(() => props.node?.type === 'dhatu')

const sandhiGroup = computed(() => props.node?.data as SandhiGroup | undefined)
const baseWord = computed(() => props.node?.data as BaseWord | undefined)
const dhatu = computed(() => props.node?.data as DhatuInfo | undefined)

function getConfidenceClass(confidence: number): string {
  if (confidence >= 0.8) return 'high'
  if (confidence >= 0.5) return 'medium'
  return 'low'
}

function formatMorphology(morph: BaseWord['morphology']): string[] {
  if (!morph) return []
  const parts: string[] = []
  if (morph.pos) parts.push(`POS: ${morph.pos}`)
  if (morph.gender) parts.push(`Gender: ${morph.gender}`)
  if (morph.number) parts.push(`Number: ${morph.number}`)
  if (morph.case) parts.push(`Case: ${morph.case}`)
  if (morph.person) parts.push(`Person: ${morph.person}`)
  if (morph.tense) parts.push(`Tense: ${morph.tense}`)
  if (morph.mood) parts.push(`Mood: ${morph.mood}`)
  if (morph.voice) parts.push(`Voice: ${morph.voice}`)
  return parts
}

function getGanaName(gana: number | undefined): string {
  if (!gana) return ''
  const ganaNames: Record<number, string> = {
    1: 'bhvādi (भ्वादि)',
    2: 'adādi (अदादि)',
    3: 'juhotyādi (जुहोत्यादि)',
    4: 'divādi (दिवादि)',
    5: 'svādi (स्वादि)',
    6: 'tudādi (तुदादि)',
    7: 'rudhādi (रुधादि)',
    8: 'tanādi (तनादि)',
    9: 'kryādi (क्र्यादि)',
    10: 'curādi (चुरादि)',
  }
  return ganaNames[gana] || `Gaṇa ${gana}`
}
</script>

<template>
  <div class="node-detail" v-if="node">
    <!-- Sandhi Group Details -->
    <div v-if="isSandhiGroup && sandhiGroup" class="detail-section">
      <h3 class="section-title">
        <span class="type-badge sandhi">Sandhi Group</span>
      </h3>

      <div class="detail-grid">
        <div class="detail-item">
          <label>Surface Form:</label>
          <span class="value devanagari">{{ sandhiGroup.surface_form }}</span>
        </div>

        <div class="detail-item" v-if="sandhiGroup.base_words.length > 0">
          <label>Word Count:</label>
          <span class="value">{{ sandhiGroup.base_words.length }}</span>
        </div>
      </div>

      <div class="word-list" v-if="sandhiGroup.base_words.length > 0">
        <label>Component Words:</label>
        <div class="word-chips">
          <span
            v-for="word in sandhiGroup.base_words"
            :key="word.word_id"
            class="word-chip"
          >
            {{ word.lemma }}
          </span>
        </div>
      </div>
    </div>

    <!-- Base Word Details -->
    <div v-if="isBaseWord && baseWord" class="detail-section">
      <h3 class="section-title">
        <span class="type-badge word">Base Word</span>
        <span
          class="confidence-badge"
          :class="getConfidenceClass(baseWord.confidence)"
        >
          {{ (baseWord.confidence * 100).toFixed(0) }}%
        </span>
      </h3>

      <div class="detail-grid">
        <div class="detail-item">
          <label>Lemma:</label>
          <span class="value devanagari">{{ baseWord.lemma }}</span>
        </div>

        <div class="detail-item">
          <label>Surface:</label>
          <span class="value devanagari">{{ baseWord.surface_form }}</span>
        </div>
      </div>

      <!-- Script Variants -->
      <div class="scripts-section" v-if="baseWord.scripts">
        <label>Script Variants:</label>
        <div class="script-grid">
          <div class="script-item">
            <span class="script-label">देवनागरी:</span>
            <span class="script-value devanagari">{{ baseWord.scripts.devanagari }}</span>
          </div>
          <div class="script-item">
            <span class="script-label">IAST:</span>
            <span class="script-value">{{ baseWord.scripts.iast }}</span>
          </div>
          <div class="script-item">
            <span class="script-label">SLP1:</span>
            <span class="script-value mono">{{ baseWord.scripts.slp1 }}</span>
          </div>
        </div>
      </div>

      <!-- Morphology -->
      <div class="morphology-section" v-if="baseWord.morphology">
        <label>Morphological Analysis:</label>
        <div class="morph-grid">
          <span
            v-for="(item, index) in formatMorphology(baseWord.morphology)"
            :key="index"
            class="morph-item"
          >
            {{ item }}
          </span>
        </div>
      </div>

      <!-- Meanings -->
      <div class="meanings-section" v-if="baseWord.meanings && baseWord.meanings.length > 0">
        <label>Meanings:</label>
        <ul class="meanings-list">
          <li v-for="(meaning, index) in baseWord.meanings" :key="index">
            {{ meaning }}
          </li>
        </ul>
      </div>

      <!-- Dhatu Reference -->
      <div class="dhatu-ref" v-if="baseWord.dhatu">
        <label>Derived from Dhātu:</label>
        <span class="dhatu-badge">√{{ baseWord.dhatu.dhatu }}</span>
        <span v-if="baseWord.dhatu.meaning" class="dhatu-meaning">
          ({{ baseWord.dhatu.meaning }})
        </span>
      </div>
    </div>

    <!-- Dhatu Details -->
    <div v-if="isDhatu && dhatu" class="detail-section">
      <h3 class="section-title">
        <span class="type-badge dhatu">Dhātu (Verbal Root)</span>
      </h3>

      <div class="detail-grid">
        <div class="detail-item">
          <label>Root:</label>
          <span class="value devanagari dhatu-root">√{{ dhatu.dhatu }}</span>
        </div>

        <div class="detail-item" v-if="dhatu.meaning">
          <label>Meaning:</label>
          <span class="value">{{ dhatu.meaning }}</span>
        </div>

        <div class="detail-item" v-if="dhatu.gana">
          <label>Gaṇa:</label>
          <span class="value">{{ getGanaName(dhatu.gana) }}</span>
        </div>

        <div class="detail-item" v-if="dhatu.pada">
          <label>Pada:</label>
          <span class="value">{{ dhatu.pada }}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Empty State -->
  <div v-else class="node-detail empty">
    <p>Click a node in the tree to see details</p>
  </div>
</template>

<style scoped>
.node-detail {
  background-color: var(--card-bg);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
  padding: 1.25rem;
}

.node-detail.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 150px;
  color: #64748b;
  font-style: italic;
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0;
  font-size: 1rem;
}

.type-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.type-badge.sandhi {
  background-color: #7c3aed;
  color: white;
}

.type-badge.word {
  background-color: #22c55e;
  color: white;
}

.type-badge.dhatu {
  background-color: #f97316;
  color: white;
}

.confidence-badge {
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
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

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.75rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.detail-item label {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 500;
}

.detail-item .value {
  font-size: 1rem;
  color: var(--text-color);
}

.devanagari {
  font-family: 'Noto Sans Devanagari', sans-serif;
}

.mono {
  font-family: 'JetBrains Mono', monospace;
}

.dhatu-root {
  font-size: 1.25rem;
  color: #f97316;
}

.scripts-section,
.morphology-section,
.meanings-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.scripts-section label,
.morphology-section label,
.meanings-section label {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 500;
}

.script-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.script-item {
  display: flex;
  gap: 0.375rem;
  font-size: 0.875rem;
}

.script-label {
  color: #64748b;
}

.script-value {
  color: var(--text-color);
}

.morph-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.morph-item {
  padding: 0.25rem 0.5rem;
  background-color: var(--bg-color);
  border-radius: 0.25rem;
  font-size: 0.8125rem;
  color: #94a3b8;
}

.meanings-list {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.875rem;
}

.meanings-list li {
  margin-bottom: 0.25rem;
}

.word-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.word-list label {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 500;
}

.word-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.word-chip {
  padding: 0.25rem 0.5rem;
  background-color: var(--bg-color);
  border-radius: 0.25rem;
  font-size: 0.875rem;
  font-family: 'Noto Sans Devanagari', sans-serif;
}

.dhatu-ref {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.dhatu-ref label {
  font-size: 0.75rem;
  color: #94a3b8;
  font-weight: 500;
}

.dhatu-badge {
  padding: 0.25rem 0.5rem;
  background-color: #f97316;
  color: white;
  border-radius: 0.25rem;
  font-family: 'Noto Sans Devanagari', sans-serif;
  font-weight: 500;
}

.dhatu-meaning {
  font-size: 0.875rem;
  color: #94a3b8;
}
</style>
