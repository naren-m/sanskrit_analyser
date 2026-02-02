/**
 * API client for Sanskrit Analyzer backend.
 */

import axios, { type AxiosInstance, type AxiosError } from 'axios'
import type { AnalysisTree, AnalysisMode } from '../stores/analysis'

// API response types
interface AnalyzeRequest {
  text: string
  mode?: AnalysisMode
  return_all_parses?: boolean
  context?: string
  engines?: string[]
  bypass_cache?: boolean
}

interface DisambiguateRequest {
  sentence_id: string
  selected_parse: string
}

interface DhatuResponse {
  id: number
  dhatu_devanagari: string
  dhatu_iast?: string
  meaning_english?: string
  meaning_hindi?: string
  gana?: number
  pada?: string
  conjugations: unknown[]
}

interface DhatuListResponse {
  count: number
  dhatus: DhatuResponse[]
}

interface DhatuSearchRequest {
  query: string
  search_type?: 'dhatu' | 'meaning' | 'all'
  limit?: number
}

interface HealthResponse {
  status: string
  version: string
  engines: string[]
  cache_enabled: boolean
}

// API Error class
export class ApiError extends Error {
  status?: number
  detail?: string

  constructor(message: string, status?: number, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

// Create axios instance
function createApiClient(baseURL: string): AxiosInstance {
  const client = axios.create({
    baseURL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // Response interceptor for error handling
  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError<{ detail?: string }>) => {
      const message = error.response?.data?.detail || error.message || 'Unknown error'
      throw new ApiError(message, error.response?.status, error.response?.data?.detail)
    }
  )

  return client
}

// Default API client
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const api = createApiClient(API_BASE_URL)

/**
 * Analyze Sanskrit text.
 */
export async function analyzeText(
  text: string,
  mode: AnalysisMode = 'production',
  options?: {
    returnAllParses?: boolean
    context?: string
    engines?: string[]
    bypassCache?: boolean
  }
): Promise<AnalysisTree> {
  const request: AnalyzeRequest = {
    text,
    mode,
    return_all_parses: options?.returnAllParses,
    context: options?.context,
    engines: options?.engines,
    bypass_cache: options?.bypassCache,
  }

  const response = await api.post<AnalysisTree>('/api/v1/analyze', request)
  return response.data
}

/**
 * Get cached analysis by sentence ID.
 */
export async function getAnalysis(sentenceId: string): Promise<AnalysisTree> {
  const response = await api.get<AnalysisTree>(`/api/v1/analyze/${sentenceId}`)
  return response.data
}

/**
 * Save disambiguation choice.
 */
export async function saveDisambiguation(
  sentenceId: string,
  selectedParse: string
): Promise<AnalysisTree> {
  const request: DisambiguateRequest = {
    sentence_id: sentenceId,
    selected_parse: selectedParse,
  }

  const response = await api.post<AnalysisTree>('/api/v1/disambiguate', request)
  return response.data
}

/**
 * Look up a dhatu by its form.
 */
export async function getDhatu(
  dhatu: string,
  includeConjugations = false
): Promise<DhatuResponse> {
  const response = await api.get<DhatuResponse>(`/api/v1/dhatu/${encodeURIComponent(dhatu)}`, {
    params: { include_conjugations: includeConjugations },
  })
  return response.data
}

/**
 * Get dhatus by gana (verb class).
 */
export async function getDhatusByGana(
  gana: number,
  limit = 100
): Promise<DhatuListResponse> {
  const response = await api.get<DhatuListResponse>(`/api/v1/dhatu/gana/${gana}`, {
    params: { limit },
  })
  return response.data
}

/**
 * Search for dhatus.
 */
export async function searchDhatus(
  query: string,
  searchType: 'dhatu' | 'meaning' | 'all' = 'all',
  limit = 20
): Promise<DhatuListResponse> {
  const request: DhatuSearchRequest = {
    query,
    search_type: searchType,
    limit,
  }

  const response = await api.post<DhatuListResponse>('/api/v1/dhatu/search', request)
  return response.data
}

/**
 * Check API health.
 */
export async function healthCheck(): Promise<HealthResponse> {
  const response = await api.get<HealthResponse>('/health')
  return response.data
}

// Export the API client for custom requests
export { api, API_BASE_URL }
