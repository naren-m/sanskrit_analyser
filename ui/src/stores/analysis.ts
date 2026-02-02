/**
 * Analysis store for managing Sanskrit text analysis state.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * Analysis mode options.
 */
export type AnalysisMode = 'production' | 'educational' | 'academic'

/**
 * Script variants for display.
 */
export interface ScriptVariants {
  devanagari: string
  iast: string
  slp1: string
  itrans?: string
}

/**
 * Morphological analysis.
 */
export interface MorphologicalTag {
  pos?: string
  gender?: string
  number?: string
  case?: string
  person?: string
  tense?: string
  mood?: string
  voice?: string
}

/**
 * Dhatu (verbal root) information.
 */
export interface DhatuInfo {
  dhatu: string
  meaning?: string
  gana?: number
  pada?: string
}

/**
 * Individual word in the analysis.
 */
export interface BaseWord {
  word_id: string
  lemma: string
  surface_form: string
  scripts?: ScriptVariants
  morphology?: MorphologicalTag
  meanings: string[]
  dhatu?: DhatuInfo
  confidence: number
}

/**
 * Sandhi group (compound or joined words).
 */
export interface SandhiGroup {
  group_id: string
  surface_form: string
  base_words: BaseWord[]
}

/**
 * Single parse interpretation.
 */
export interface ParseTree {
  parse_id: string
  confidence: number
  sandhi_groups: SandhiGroup[]
  is_selected: boolean
}

/**
 * Confidence metrics.
 */
export interface ConfidenceMetrics {
  overall: number
  engine_agreement: number
  disambiguation_score?: number
}

/**
 * Complete analysis result.
 */
export interface AnalysisTree {
  sentence_id: string
  original_text: string
  normalized_slp1: string
  scripts: ScriptVariants
  parse_forest: ParseTree[]
  confidence: ConfidenceMetrics
  mode: string
  cached_at?: string
  cache_tier?: string
  needs_human_review: boolean
  engine_details?: Record<string, unknown>
}

/**
 * Store state.
 */
export const useAnalysisStore = defineStore('analysis', () => {
  // State
  const inputText = ref('')
  const mode = ref<AnalysisMode>('production')
  const displayScript = ref<'devanagari' | 'iast' | 'slp1'>('devanagari')
  const result = ref<AnalysisTree | null>(null)
  const currentParseIndex = ref(0)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const currentParse = computed(() => {
    if (!result.value || result.value.parse_forest.length === 0) {
      return null
    }
    return result.value.parse_forest[currentParseIndex.value]
  })

  const parseCount = computed(() => {
    return result.value?.parse_forest.length ?? 0
  })

  const hasMultipleParses = computed(() => {
    return parseCount.value > 1
  })

  // Actions
  function setInputText(text: string) {
    inputText.value = text
  }

  function setMode(newMode: AnalysisMode) {
    mode.value = newMode
  }

  function setDisplayScript(script: 'devanagari' | 'iast' | 'slp1') {
    displayScript.value = script
  }

  function setResult(analysisResult: AnalysisTree) {
    result.value = analysisResult
    currentParseIndex.value = 0
    error.value = null
  }

  function setLoading(loading: boolean) {
    isLoading.value = loading
  }

  function setError(errorMessage: string | null) {
    error.value = errorMessage
  }

  function nextParse() {
    if (result.value && currentParseIndex.value < result.value.parse_forest.length - 1) {
      currentParseIndex.value++
    }
  }

  function previousParse() {
    if (currentParseIndex.value > 0) {
      currentParseIndex.value--
    }
  }

  function selectParse(index: number) {
    if (result.value && index >= 0 && index < result.value.parse_forest.length) {
      currentParseIndex.value = index
    }
  }

  function reset() {
    result.value = null
    currentParseIndex.value = 0
    error.value = null
    isLoading.value = false
  }

  return {
    // State
    inputText,
    mode,
    displayScript,
    result,
    currentParseIndex,
    isLoading,
    error,
    // Getters
    currentParse,
    parseCount,
    hasMultipleParses,
    // Actions
    setInputText,
    setMode,
    setDisplayScript,
    setResult,
    setLoading,
    setError,
    nextParse,
    previousParse,
    selectParse,
    reset,
  }
})
