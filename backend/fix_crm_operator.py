def fix():
    with open("backend/app/services/crm_operator_service.py", "r", encoding="utf-8") as f:
        c = f.read()

    old = """        # Only merge persistent state into context if context lost or matching operation
        if not ctx.get("operation") and not ctx.get("draft"):
            for k, v in state_dto.collected_fields.items():
                if k not in ctx:
                    ctx[k] = v
        elif ctx.get("operation") == CRMOperationType.CREATE_LEAD.value:
            ctx.pop("lead_id", None)
            state_dto.collected_fields.pop("lead_id", None)"""

    new = """        # If client passes explicit context (e.g. with draft or lead_id),
        # only fill in missing fields from state_dto if they don't contradict the current draft
        if not ctx.get("operation") and not ctx.get("draft"):
            for k, v in state_dto.collected_fields.items():
                if k not in ctx:
                    ctx[k] = v
        elif "draft" in ctx:
            ctx.pop("lead_id", None)"""

    c = c.replace(old, new, 1)

    with open("backend/app/services/crm_operator_service.py", "w", encoding="utf-8") as f:
        f.write(c)
    print("Fixed crm_operator_service.py")

if __name__ == "__main__":
    fix()

