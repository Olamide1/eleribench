/**
 * Eleri shared types — mirrors schemas/json/*.schema.json.
 * Source of truth for taxonomy is this file + the JSON Schemas; keep in sync manually
 * (Phase 0 is small enough that codegen isn't worth it yet).
 */

// ---------- Taxonomies (PRD §3.2, §3.3, Appendix C.2) ----------

export const SPEND_CATEGORIES = [
  "compute_inference",
  "data_api",
  "storage_bandwidth",
  "saas_subscription",
  "software_tools",
  "content_media",
  "communications",
  "advertising_promotion",
  "commerce_goods",
  "commerce_services",
  "travel_logistics",
  "financial_fees",
  "network_gas_fees",
  "human_services",
  "deposits_transfers",
  "other_unclassified",
] as const;

export type SpendCategory = (typeof SPEND_CATEGORIES)[number];

export const BLOCKING_ANOMALIES = [
  "amount_exceeds_mandate",
  "vendor_not_allowed",
  "mandate_expired",
  "no_matching_mandate",
  "purpose_mismatch",
  "duplicate_charge",
  // Appendix C — chain-specific, all blocking
  "address_poisoning_lookalike",
  "wrong_network_or_token",
  "settlement_not_found",
] as const;

export const WARNING_ANOMALIES = [
  "budget_period_at_risk",
  "velocity_anomaly",
  "amount_discrepancy",
  "currency_mismatch",
  "split_transaction_pattern",
  "stale_settlement",
] as const;

export const ANOMALIES = [...BLOCKING_ANOMALIES, ...WARNING_ANOMALIES] as const;

export type BlockingAnomaly = (typeof BLOCKING_ANOMALIES)[number];
export type WarningAnomaly = (typeof WARNING_ANOMALIES)[number];
export type Anomaly = (typeof ANOMALIES)[number];

export const VERDICTS = ["match", "mismatch", "unverifiable"] as const;
export type Verdict = (typeof VERDICTS)[number];

export const MANDATE_PERIODS = ["one_time", "daily", "weekly", "monthly", "annual"] as const;
export type MandatePeriod = (typeof MANDATE_PERIODS)[number];

export const PAYMENT_PROTOCOLS = ["x402", "ap2", "acp", "stripe", "other"] as const;
export type PaymentProtocol = (typeof PAYMENT_PROTOCOLS)[number];

export const SETTLEMENT_STATUSES = ["settled", "pending", "not_found"] as const;
export type SettlementStatus = (typeof SETTLEMENT_STATUSES)[number];

// ---------- Input: TransactionRecord ----------

export interface Mandate {
  mandate_id?: string;
  budget?: {
    amount: number;
    currency: string;
    period: MandatePeriod;
  };
  /** Domains, wildcards, wallet addresses, or ENS/Basenames. */
  allowed_vendors?: string[];
  denied_vendors?: string[];
  allowed_purposes?: string[];
  /** ISO 8601 */
  expiry?: string;
  /** ISO 8601 */
  created_at?: string;
}

export interface ToolCall {
  tool?: string;
  args?: Record<string, unknown>;
  timestamp?: string;
}

export interface Activity {
  agent_id?: string;
  agent_name?: string;
  intent?: string;
  tool_calls?: ToolCall[];
  window_start?: string;
  window_end?: string;
}

export interface FeeBreakdown {
  gas?: number;
  facilitator_fee?: number;
}

export interface Payment {
  protocol?: PaymentProtocol;
  amount?: number;
  currency?: string;
  vendor?: string;
  /** ISO 8601 */
  timestamp?: string;
  reference?: string;
  // Appendix C — on-chain settlement fields, present only for chain-settled payments
  chain?: string;
  tx_hash?: string;
  token_contract?: string;
  token_decimals?: number;
  counterparty_address?: string;
  /** Set by the deterministic pre-check layer, never guessed by the model. */
  settlement_status?: SettlementStatus;
  fee_breakdown?: FeeBreakdown;
}

export interface TransactionRecord {
  mandate?: Mandate;
  activity?: Activity;
  payment?: Payment;
}

// ---------- Output: EleriVerdict ----------

export interface EleriVerdict {
  verdict: Verdict;
  category: SpendCategory;
  anomalies: Anomaly[];
  confidence: number; // 0..1
  /** One sentence, max ~30 tokens, citing the decisive field(s). */
  reason: string;
}

// ---------- Business-rule helpers (mirrors schemas/python/models.py) ----------

export function hasBlockingAnomaly(anomalies: Anomaly[]): boolean {
  return anomalies.some((a) => (BLOCKING_ANOMALIES as readonly string[]).includes(a));
}

/** Cheap structural sanity check beyond what JSON Schema alone enforces. */
export function isConsistentVerdict(v: EleriVerdict): boolean {
  if (v.verdict === "match" && hasBlockingAnomaly(v.anomalies)) return false;
  return true;
}
