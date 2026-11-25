from typing import Tuple, List, Dict, Any
from datetime import datetime
from backend.app.models.models import Lead, PriorityLevel, PipelineStage


def calculate_lead_score(lead: Lead) -> Tuple[int, List[Dict[str, Any]], PriorityLevel]:
    """
    Computes an explainable lead conversion readiness score (0-100)
    along with contributing factors and auto-calculated priority.
    """
    if lead.do_not_contact:
        return 0, [{"factor": "Do Not Contact", "impact": -100, "description": "Customer requested no contact"}], PriorityLevel.LOW

    score = 40  # Base score
    factors = []

    # 1. Purchase Timeline
    timeline = (lead.purchase_timeline or "").lower()
    if "immediate" in timeline or "1 month" in timeline:
        score += 25
        factors.append({"factor": "Immediate Purchase Timeline", "impact": 25, "description": "Looking to buy within 30 days"})
    elif "1-3" in timeline or "quarter" in timeline:
        score += 15
        factors.append({"factor": "Short Purchase Timeline", "impact": 15, "description": "Buying in 1-3 months"})
    elif "6" in timeline or "future" in timeline:
        score += 5
        factors.append({"factor": "Long-term Planning", "impact": 5, "description": "Horizon over 6 months"})

    # 2. Financial Readiness / Budget
    if lead.budget_max and lead.budget_max > 0:
        score += 15
        factors.append({"factor": "Defined Budget", "impact": 15, "description": f"Verified budget up to {lead.budget_max:,.0f}"})
    if lead.down_payment_budget and lead.down_payment_budget > 0:
        score += 10
        factors.append({"factor": "Ready Down Payment", "impact": 10, "description": f"Cash ready: {lead.down_payment_budget:,.0f}"})

    # 3. Pipeline Stage Engagement
    if lead.pipeline_stage in [PipelineStage.VISIT_COMPLETED, PipelineStage.NEGOTIATION, PipelineStage.RESERVATION]:
        score += 25
        factors.append({"factor": "High Stage Advancement", "impact": 25, "description": f"Reached {lead.pipeline_stage.value}"})
    elif lead.pipeline_stage in [PipelineStage.VISIT_SCHEDULED, PipelineStage.QUALIFIED, PipelineStage.INTERESTED]:
        score += 15
        factors.append({"factor": "Active Engagement", "impact": 15, "description": f"In {lead.pipeline_stage.value}"})

    # 4. Activity & Follow-up Health
    if not lead.next_followup_date:
        score -= 15
        factors.append({"factor": "No Next Follow-up", "impact": -15, "description": "Risk of stalled lead with no scheduled action"})

    final_score = max(5, min(98, score))

    # Priority mapping
    if final_score >= 80:
        priority = PriorityLevel.URGENT
    elif final_score >= 65:
        priority = PriorityLevel.HIGH
    elif final_score >= 45:
        priority = PriorityLevel.MEDIUM
    else:
        priority = PriorityLevel.LOW

    return final_score, factors, priority
