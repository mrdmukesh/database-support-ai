import type { ConnectionValidationResult } from "../../models/connection";

interface ConnectionTestResultProps {
  isTesting?: boolean;
  result?: ConnectionValidationResult;
  error?: string;
}

export function ConnectionTestResult({ isTesting = false, result, error }: ConnectionTestResultProps) {
  if (isTesting) return <span className="connection-test pending">Testing...</span>;
  if (error) return <span className="connection-test error" role="alert">{error}</span>;
  if (result) {
    return (
      <span className={`connection-test ${result.is_valid ? "success" : "error"}`} role="status">
        {result.message}
      </span>
    );
  }
  return <span className="connection-test">Not tested</span>;
}
