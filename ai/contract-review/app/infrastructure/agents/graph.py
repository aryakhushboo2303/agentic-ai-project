import json
import re
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from app.core.logging import get_logger
from app.domain.ports import LLMClient

logger = get_logger(__name__)


class ContractAnalysisState(TypedDict):
    contract_id: str
    full_text: str
    chunks: list[dict]
    clauses: list[dict]
    risks: list[dict]
    compliance: list[dict]
    summary: dict
    errors: list[str]


def _extract_json(text: str) -> dict | list:
    """Parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        text = match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise


class ContractAnalysisGraph:
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(ContractAnalysisState)
        graph.add_node("clause_extractor", self._clause_extractor)
        graph.add_node("risk_assessor", self._risk_assessor)
        graph.add_node("compliance_checker", self._compliance_checker)
        graph.add_node("summarizer", self._summarizer)

        graph.add_edge(START, "clause_extractor")
        graph.add_edge("clause_extractor", "risk_assessor")
        graph.add_edge("risk_assessor", "compliance_checker")
        graph.add_edge("compliance_checker", "summarizer")
        graph.add_edge("summarizer", END)

        return graph.compile()

    async def run(self, contract_id: UUID, full_text: str, chunks: list[dict]) -> dict:
        initial: ContractAnalysisState = {
            "contract_id": str(contract_id),
            "full_text": full_text[:12000],
            "chunks": chunks,
            "clauses": [],
            "risks": [],
            "compliance": [],
            "summary": {},
            "errors": [],
        }
        logger.info("analysis_graph_start", contract_id=str(contract_id))
        result = await self._graph.ainvoke(initial)
        logger.info("analysis_graph_complete", contract_id=str(contract_id))
        return result

    async def _clause_extractor(self, state: ContractAnalysisState) -> dict:
        system = (
            "You are a legal contract analyst. Extract key clauses from the contract. "
            "Return ONLY valid JSON array with objects: "
            '{"title": str, "text": str, "category": str, "confidence": float, "page_number": int|null}'
        )
        user = f"Extract clauses from this contract:\n\n{state['full_text']}"
        try:
            response = await self._llm.chat(system, user)
            clauses = _extract_json(response)
            if isinstance(clauses, dict):
                clauses = clauses.get("clauses", [])
            logger.info("clause_extraction_done", count=len(clauses))
            return {"clauses": clauses}
        except Exception as e:
            logger.error("clause_extraction_failed", error=str(e))
            return {"clauses": [], "errors": state["errors"] + [f"clause_extractor: {e}"]}

    async def _risk_assessor(self, state: ContractAnalysisState) -> dict:
        clauses_text = json.dumps(state["clauses"][:10], indent=2)
        system = (
            "You are a contract risk analyst. Identify risks in the contract. "
            "Return ONLY valid JSON array with objects: "
            '{"clause_ref": str, "severity": "low|medium|high|critical", '
            '"description": str, "recommendation": str}'
        )
        user = f"Clauses:\n{clauses_text}\n\nContract excerpt:\n{state['full_text'][:6000]}"
        try:
            response = await self._llm.chat(system, user)
            risks = _extract_json(response)
            if isinstance(risks, dict):
                risks = risks.get("risks", [])
            logger.info("risk_assessment_done", count=len(risks))
            return {"risks": risks}
        except Exception as e:
            logger.error("risk_assessment_failed", error=str(e))
            return {"risks": [], "errors": state["errors"] + [f"risk_assessor: {e}"]}

    async def _compliance_checker(self, state: ContractAnalysisState) -> dict:
        system = (
            "You are a compliance reviewer. Check the contract against standard business "
            "compliance areas: data privacy, termination rights, liability caps, IP ownership, "
            "governing law. Return ONLY valid JSON array with objects: "
            '{"regulation": str, "status": "pass|fail|partial", "details": str}'
        )
        user = f"Review compliance for:\n{state['full_text'][:6000]}"
        try:
            response = await self._llm.chat(system, user)
            compliance = _extract_json(response)
            if isinstance(compliance, dict):
                compliance = compliance.get("compliance", [])
            logger.info("compliance_check_done", count=len(compliance))
            return {"compliance": compliance}
        except Exception as e:
            logger.error("compliance_check_failed", error=str(e))
            return {"compliance": [], "errors": state["errors"] + [f"compliance_checker: {e}"]}

    async def _summarizer(self, state: ContractAnalysisState) -> dict:
        system = (
            "You are a contract summarizer. Produce an executive summary. "
            "Return ONLY valid JSON object: "
            '{"executive_summary": str, "key_terms": {"parties": str, "term": str, '
            '"payment": str, "termination": str, "governing_law": str}}'
        )
        context = (
            f"Clauses count: {len(state['clauses'])}\n"
            f"Risks count: {len(state['risks'])}\n"
            f"Contract:\n{state['full_text'][:6000]}"
        )
        try:
            response = await self._llm.chat(system, context)
            summary = _extract_json(response)
            if isinstance(summary, list):
                summary = {"executive_summary": str(summary), "key_terms": {}}
            logger.info("summarization_done")
            return {"summary": summary}
        except Exception as e:
            logger.error("summarization_failed", error=str(e))
            return {
                "summary": {"executive_summary": "Summary unavailable.", "key_terms": {}},
                "errors": state["errors"] + [f"summarizer: {e}"],
            }
