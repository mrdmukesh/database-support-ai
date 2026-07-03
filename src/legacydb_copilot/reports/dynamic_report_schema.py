from __future__ import annotations

from dataclasses import dataclass

from legacydb_copilot.agents.entity_extraction_agent import ExtractedEntity
from legacydb_copilot.agents.intent_agent import IntentResult
from legacydb_copilot.agents.hypothesis_agent import HypothesisReasoningResult
from legacydb_copilot.agents.object_ranking_agent import RankedObject
from legacydb_copilot.agents.recommendation_agent import RecommendationResult
from legacydb_copilot.agents.reasoning_agent import ReasoningResult
from legacydb_copilot.services.evidence_correlation_service import CorrelatedEvidence
from legacydb_copilot.services.evidence_execution_service import EvidenceResult
from legacydb_copilot.services.evidence_focus_service import EvidenceFocus
from legacydb_copilot.services.evidence_gate_service import EvidenceGateResult
from legacydb_copilot.services.evidence_verification_agent import SuggestedVerificationCheck, VerificationResult
from legacydb_copilot.services.metadata_search_service import MetadataSearchResult
from legacydb_copilot.services.rag_retrieval_service import RetrievedDocument
from legacydb_copilot.services.stored_procedure_intelligence import ProcedureAnalysis


@dataclass(frozen=True)
class DynamicInvestigationBundle:
    question: str
    intent: IntentResult
    entities: list[ExtractedEntity]
    ranked_objects: list[RankedObject]
    metadata: MetadataSearchResult
    evidence: list[EvidenceResult]
    correlated_evidence: list[CorrelatedEvidence]
    procedure_analysis: list[ProcedureAnalysis]
    hypothesis_reasoning: HypothesisReasoningResult
    documents: list[RetrievedDocument]
    reasoning: ReasoningResult
    recommendation: RecommendationResult
    confidence: float
    evidence_focus: EvidenceFocus | None = None
    evidence_gate: EvidenceGateResult | None = None
    confidence_factors: list[str] | None = None
    investigation_mode: str = "INVESTIGATION"
    mode_rationale: str = ""
    ai_reasoning_status: dict[str, str] | None = None
    verification_checks: list[SuggestedVerificationCheck] | None = None
    verification_results: list[VerificationResult] | None = None
