import type { AskResponse } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function askQuestion(
  question: string,
  signal?: AbortSignal,
): Promise<AskResponse> {
  const response = await fetch(`${API_BASE_URL}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
    signal,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message =
      body?.error?.message ??
      body?.detail?.message ??
      body?.detail ??
      `Ask request failed with status ${response.status}.`;
    throw new Error(typeof message === "string" ? message : "Request failed.");
  }

  return response.json() as Promise<AskResponse>;
}
