import { useContext } from "react";

import { InvestigationContext } from "./investigation-context";

export function useInvestigation() {
  const context = useContext(InvestigationContext);
  if (!context) {
    throw new Error("useInvestigation must be used within an InvestigationProvider");
  }
  return context;
}
