def update_state_manager():
    with open("backend/app/services/conversation_state_manager.py", "r", encoding="utf-8") as f:
        c = f.read()

    old_merge = """    @classmethod
    def _merge_legacy_into_dto(cls, dto: ConversationStateDTO, legacy: Dict[str, Any]) -> None:
        for k, v in legacy.items():"""

    new_merge = """    @classmethod
    def _merge_legacy_into_dto(cls, dto: ConversationStateDTO, legacy: Dict[str, Any]) -> None:
        if legacy.get("operation") == "CREATE_LEAD" and "lead_id" not in legacy:
            dto.collected_fields.pop("lead_id", None)
        for k, v in legacy.items():"""

    c = c.replace(old_merge, new_merge, 1)

    with open("backend/app/services/conversation_state_manager.py", "w", encoding="utf-8") as f:
        f.write(c)

def update_crm_operator():
    with open("backend/app/services/crm_operator_service.py", "r", encoding="utf-8") as f:
        c = f.read()

    old_merge = """        # Merge persistent state into context if context lost
        for k, v in state_dto.collected_fields.items():
            if k not in ctx:
                ctx[k] = v"""

    new_merge = """        # Only merge persistent state into context if context lost or matching operation
        if not ctx.get("operation") and not ctx.get("draft"):
            for k, v in state_dto.collected_fields.items():
                if k not in ctx:
                    ctx[k] = v
        elif ctx.get("operation") == CRMOperationType.CREATE_LEAD.value:
            ctx.pop("lead_id", None)
            state_dto.collected_fields.pop("lead_id", None)"""

    c = c.replace(old_merge, new_merge, 1)

    with open("backend/app/services/crm_operator_service.py", "w", encoding="utf-8") as f:
        f.write(c)

if __name__ == "__main__":
    update_state_manager()
    update_crm_operator()
    print("Updated state manager and crm operator.")

