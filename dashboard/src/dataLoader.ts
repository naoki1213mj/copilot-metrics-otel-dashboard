import type { DailySummary, LanguageSummary, UserDailySummary } from './types';

interface DashboardRuntimeConfig {
  dataEndpoints?: string[] | null;
}

export interface DashboardDataSets {
  daily: DailySummary[];
  languageSummary: LanguageSummary[];
  userDaily: UserDailySummary[];
}

const DEFAULT_DATA_ENDPOINTS = ['/data'] as const;
const RUNTIME_CONFIG_PATH = '/runtime-config.json';

const DATASET_FILES = {
  daily: 'daily_summary.json',
  languageSummary: 'language_summary.json',
  userDaily: 'user_daily_summary.json',
} satisfies Record<keyof DashboardDataSets, string>;

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function ensureTrailingSlash(value: string): string {
  return value.endsWith('/') ? value : `${value}/`;
}

function resolveDatasetUrl(endpoint: string, fileName: string): string {
  const appBaseUrl = new URL(import.meta.env.BASE_URL, window.location.origin);
  const endpointUrl = new URL(ensureTrailingSlash(endpoint), appBaseUrl);
  return new URL(fileName, endpointUrl).toString();
}

function normalizeDataEndpoints(config: DashboardRuntimeConfig | null): string[] {
  const configuredEndpoints = config?.dataEndpoints?.filter(isNonEmptyString) ?? [];

  if (configuredEndpoints.length > 0) {
    return [...new Set(configuredEndpoints)];
  }

  return [...DEFAULT_DATA_ENDPOINTS];
}

async function loadRuntimeConfig(): Promise<DashboardRuntimeConfig | null> {
  try {
    const response = await fetch(RUNTIME_CONFIG_PATH, { cache: 'no-store' });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as DashboardRuntimeConfig;
  } catch {
    return null;
  }
}

async function fetchDataset<T>(fileName: string, endpoints: string[]): Promise<T> {
  const errors: string[] = [];

  for (const endpoint of endpoints) {
    const url = resolveDatasetUrl(endpoint, fileName);

    try {
      const response = await fetch(url, {
        headers: {
          Accept: 'application/json',
        },
      });

      if (!response.ok) {
        errors.push(`${url}: ${response.status}`);
        continue;
      }

      return (await response.json()) as T;
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      errors.push(`${url}: ${message}`);
    }
  }

  throw new Error(`${fileName} を取得できませんでした (${errors.join(', ')})`);
}

export async function loadDashboardData(): Promise<DashboardDataSets> {
  const runtimeConfig = await loadRuntimeConfig();
  const dataEndpoints = normalizeDataEndpoints(runtimeConfig);

  const [daily, languageSummary, userDaily] = await Promise.all([
    fetchDataset<DailySummary[]>(DATASET_FILES.daily, dataEndpoints),
    fetchDataset<LanguageSummary[]>(DATASET_FILES.languageSummary, dataEndpoints),
    fetchDataset<UserDailySummary[]>(DATASET_FILES.userDaily, dataEndpoints),
  ]);

  return {
    daily,
    languageSummary,
    userDaily,
  };
}
