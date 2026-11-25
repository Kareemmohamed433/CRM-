def patch():
    with open("backend/app/services/crm_operator_service.py", "r", encoding="utf-8") as f:
        c = f.read()

    # 1. Update _ROUTER_INTENTS
    old_dict = """        "create_lead": CRMOperationType.CREATE_LEAD,
        "log_activity": CRMOperationType.GENERAL_QUESTION,
        "general": CRMOperationType.GENERAL_QUESTION,"""

    new_dict = """        "create_lead": CRMOperationType.CREATE_LEAD,
        "sales_summary": CRMOperationType.SALES_SUMMARY,
        "team_performance": CRMOperationType.TEAM_PERFORMANCE,
        "customer_pipeline": CRMOperationType.CUSTOMER_PIPELINE,
        "customer_history": CRMOperationType.CUSTOMER_HISTORY,
        "property_offer": CRMOperationType.PROPERTY_OFFER,
        "log_activity": CRMOperationType.GENERAL_QUESTION,
        "general": CRMOperationType.GENERAL_QUESTION,"""

    c = c.replace(old_dict, new_dict, 1)

    # 2. Update _route_intent
    old_ret = """        if rule_intent in self._CREATE_INTENTS:
            return rule_intent, routed          # explicit write verbs in the text win
        if llm_intent in self._LLM_BLOCKED_ACTIONS:
            return rule_intent, routed          # never auto-start an immediate-save action
        return llm_intent, routed"""

    new_ret = """        if rule_intent in self._CREATE_INTENTS:
            return rule_intent, routed          # explicit write verbs in the text win
        if llm_intent in self._LLM_BLOCKED_ACTIONS:
            return rule_intent, routed          # never auto-start an immediate-save action
        if llm_intent == CRMOperationType.GENERAL_QUESTION and rule_intent != CRMOperationType.GENERAL_QUESTION:
            return rule_intent, routed          # specialized rules win over general fallback
        return llm_intent, routed"""

    c = c.replace(old_ret, new_ret, 1)

    with open("backend/app/services/crm_operator_service.py", "w", encoding="utf-8") as f:
        f.write(c)

    print("Patched router intent handling.")

if __name__ == "__main__":
    patch()

