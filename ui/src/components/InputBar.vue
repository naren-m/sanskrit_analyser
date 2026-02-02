<script setup lang="ts">
import { computed } from 'vue'
import { useAnalysisStore, type AnalysisMode } from '../stores/analysis'

const store = useAnalysisStore()

const emit = defineEmits<{
  analyze: [text: string, mode: AnalysisMode]
}>()

const canAnalyze = computed(() => {
  return store.inputText.trim().length > 0 && !store.isLoading
})

function handleAnalyze() {
  if (canAnalyze.value) {
    emit('analyze', store.inputText, store.mode)
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleAnalyze()
  }
}
</script>

<template>
  <div class="input-bar">
    <div class="input-row">
      <input
        v-model="store.inputText"
        type="text"
        class="text-input"
        placeholder="संस्कृत वाक्यं लिखतु... (Enter Sanskrit text)"
        :disabled="store.isLoading"
        @keydown="handleKeydown"
      />

      <button
        class="analyze-btn"
        :disabled="!canAnalyze"
        @click="handleAnalyze"
      >
        <span v-if="store.isLoading" class="loading-spinner"></span>
        <span v-else>विश्लेषयतु</span>
      </button>
    </div>

    <div class="controls-row">
      <div class="control-group">
        <label for="mode-select">Mode:</label>
        <select
          id="mode-select"
          v-model="store.mode"
          class="mode-select"
          :disabled="store.isLoading"
        >
          <option value="production">Production</option>
          <option value="educational">Educational</option>
          <option value="academic">Academic</option>
        </select>
      </div>

      <div class="control-group">
        <label for="script-select">Script:</label>
        <select
          id="script-select"
          v-model="store.displayScript"
          class="script-select"
        >
          <option value="devanagari">देवनागरी</option>
          <option value="iast">IAST</option>
          <option value="slp1">SLP1</option>
        </select>
      </div>

      <div class="control-group examples">
        <label>Examples:</label>
        <button
          class="example-btn"
          @click="store.setInputText('रामः गच्छति')"
        >
          रामः गच्छति
        </button>
        <button
          class="example-btn"
          @click="store.setInputText('धर्मक्षेत्रे कुरुक्षेत्रे')"
        >
          धर्मक्षेत्रे...
        </button>
        <button
          class="example-btn"
          @click="store.setInputText('अहं ब्रह्मास्मि')"
        >
          अहं ब्रह्मास्मि
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.input-bar {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
  background-color: var(--card-bg);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
}

.input-row {
  display: flex;
  gap: 1rem;
}

.text-input {
  flex: 1;
  padding: 0.875rem 1rem;
  font-size: 1.25rem;
  font-family: 'Noto Sans Devanagari', 'Noto Sans', sans-serif;
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  background-color: var(--bg-color);
  color: var(--text-color);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.text-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.2);
}

.text-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.text-input::placeholder {
  color: #64748b;
}

.analyze-btn {
  padding: 0.875rem 2rem;
  font-size: 1.125rem;
  font-weight: 600;
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background-color 0.2s, transform 0.1s;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 140px;
  justify-content: center;
}

.analyze-btn:hover:not(:disabled) {
  background-color: #ea580c;
  transform: translateY(-1px);
}

.analyze-btn:active:not(:disabled) {
  transform: translateY(0);
}

.analyze-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.controls-row {
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
  align-items: center;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.control-group label {
  font-size: 0.875rem;
  color: #94a3b8;
  font-weight: 500;
}

.mode-select,
.script-select {
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background-color: var(--bg-color);
  color: var(--text-color);
  cursor: pointer;
}

.mode-select:focus,
.script-select:focus {
  outline: none;
  border-color: var(--primary-color);
}

.examples {
  margin-left: auto;
}

.example-btn {
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
  font-family: 'Noto Sans Devanagari', sans-serif;
  background-color: transparent;
  color: var(--primary-color);
  border: 1px solid var(--primary-color);
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
}

.example-btn:hover {
  background-color: var(--primary-color);
  color: white;
}

@media (max-width: 768px) {
  .controls-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .examples {
    margin-left: 0;
    margin-top: 0.5rem;
  }

  .input-row {
    flex-direction: column;
  }

  .analyze-btn {
    width: 100%;
  }
}
</style>
