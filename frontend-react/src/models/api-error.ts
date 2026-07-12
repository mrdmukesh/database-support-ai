export interface FastApiValidationIssue {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
  [key: string]: unknown;
}

export interface ApiErrorBody {
  detail?: string | FastApiValidationIssue[] | Record<string, unknown> | unknown;
  [key: string]: unknown;
}

export interface ApiErrorLike {
  status: number;
  body: unknown;
}
