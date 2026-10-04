export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function gql<T>(query: string, variables: Record<string, unknown> = {}): Promise<T> {
  const res = await fetch(`${API}/graphql`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query, variables }),
  });
  const body = await res.json();
  if (body.errors?.length) throw new Error(body.errors[0].message);
  return body.data as T;
}

export interface Summary {
  reportsInWindow: number;
  analysable: number;
  reportedBbl: number;
  windowStart: string;
  windowEnd: string;
}

export interface Explanation {
  spill: {
    id: string;
    operator: string | null;
    incidentDate: string | null;
    causeLabel: string | null;
    quantityBbl: number | null;
    siteName: string | null;
    issues: { code: string; severity: "error" | "warning" | "info"; message: string }[];
  };
  steps: { step: string; outcome: string }[];
  rawRecord: Record<string, unknown> | null;
}

export const SUMMARY_QUERY = `{ summary { reportsInWindow analysable reportedBbl windowStart windowEnd } }`;

export const EXPLAIN_QUERY = `query($id: ID!) {
  explainSpill(id: $id) {
    spill { id operator incidentDate causeLabel quantityBbl siteName
            issues { code severity message } }
    steps { step outcome }
    rawRecord
  }
}`;
