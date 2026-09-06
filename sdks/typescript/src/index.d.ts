export interface ImplementationIdentity {
  name: string;
  version: string;
  language: string;
}

export interface ConformanceSummary {
  readonly valid: true;
  readonly suiteId: "cgqa-liminalqa-v0.1";
  readonly implementation: Readonly<ImplementationIdentity>;
  readonly passed: 14;
  readonly mayAuthorizeAction: false;
  readonly claimBoundary: string;
}

export class ConformanceReportError extends Error {}
export function validateConformanceReport(report: unknown): ConformanceSummary;
export function validateConformanceReportJson(raw: string): ConformanceSummary;
export const protocol: Readonly<{
  schema: string;
  suiteId: "cgqa-liminalqa-v0.1";
  suiteVersion: "0.1.0";
  suiteSha256: string;
  maxReportBytes: number;
  mayAuthorizeAction: false;
}>;
