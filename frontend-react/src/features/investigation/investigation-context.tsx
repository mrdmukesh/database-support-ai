import {
  createContext,
  useCallback,
  useMemo,
  useReducer,
  type ReactNode,
} from "react";

import type { InvestigationSubmitResponse } from "../../models/investigation";

export interface InvestigationState {
  selectedWorkspaceId: string | null;
  selectedConnectionId: string | null;
  submittedQuestion: string | null;
  isLoading: boolean;
  currentInvestigationId: string | null;
  currentConversationId: string | null;
  currentResponse: InvestigationSubmitResponse | null;
  currentError: string | null;
}

export interface InvestigationContextValue extends InvestigationState {
  selectWorkspace: (workspaceId: string | null) => void;
  selectConnection: (connectionId: string | null) => void;
  startSubmission: (question: string) => void;
  completeSubmission: (response: InvestigationSubmitResponse) => void;
  failSubmission: (error: string) => void;
  reset: () => void;
}

export const initialInvestigationState: InvestigationState = {
  selectedWorkspaceId: null,
  selectedConnectionId: null,
  submittedQuestion: null,
  isLoading: false,
  currentInvestigationId: null,
  currentConversationId: null,
  currentResponse: null,
  currentError: null,
};

type Action =
  | { type: "select-workspace"; workspaceId: string | null }
  | { type: "select-connection"; connectionId: string | null }
  | { type: "start"; question: string }
  | { type: "success"; response: InvestigationSubmitResponse }
  | { type: "failure"; error: string }
  | { type: "reset" };

function reducer(state: InvestigationState, action: Action): InvestigationState {
  switch (action.type) {
    case "select-workspace":
      return {
        ...state,
        selectedWorkspaceId: action.workspaceId,
        selectedConnectionId:
          action.workspaceId === state.selectedWorkspaceId ? state.selectedConnectionId : null,
      };
    case "select-connection":
      return { ...state, selectedConnectionId: action.connectionId };
    case "start":
      return {
        ...state,
        submittedQuestion: action.question,
        isLoading: true,
        currentInvestigationId: null,
        currentResponse: null,
        currentError: null,
      };
    case "success":
      return {
        ...state,
        isLoading: false,
        currentInvestigationId: action.response.investigation_id,
        currentConversationId: action.response.conversation.id,
        currentResponse: action.response,
        currentError: null,
      };
    case "failure":
      return {
        ...state,
        isLoading: false,
        currentInvestigationId: null,
        currentResponse: null,
        currentError: action.error,
      };
    case "reset":
      return initialInvestigationState;
  }
}

export const InvestigationContext = createContext<InvestigationContextValue | null>(null);

export function InvestigationProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialInvestigationState);
  const selectWorkspace = useCallback(
    (workspaceId: string | null) => dispatch({ type: "select-workspace", workspaceId }),
    [],
  );
  const selectConnection = useCallback(
    (connectionId: string | null) => dispatch({ type: "select-connection", connectionId }),
    [],
  );
  const startSubmission = useCallback(
    (question: string) => dispatch({ type: "start", question }),
    [],
  );
  const completeSubmission = useCallback(
    (response: InvestigationSubmitResponse) => dispatch({ type: "success", response }),
    [],
  );
  const failSubmission = useCallback(
    (error: string) => dispatch({ type: "failure", error }),
    [],
  );
  const reset = useCallback(() => dispatch({ type: "reset" }), []);

  const value = useMemo(
    () => ({
      ...state,
      selectWorkspace,
      selectConnection,
      startSubmission,
      completeSubmission,
      failSubmission,
      reset,
    }),
    [state, selectWorkspace, selectConnection, startSubmission, completeSubmission, failSubmission, reset],
  );

  return <InvestigationContext.Provider value={value}>{children}</InvestigationContext.Provider>;
}
