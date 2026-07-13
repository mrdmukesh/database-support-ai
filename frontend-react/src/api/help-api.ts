import { apiRequest } from "./client";
import type { HelpResponse } from "../models/help";

export async function askApplicationHelp(question: string, currentPage: string, signal?: AbortSignal): Promise<HelpResponse> {
  return (await apiRequest<HelpResponse>("/help/ask", { method: "POST", body: { question, current_page: currentPage }, signal }))!;
}
