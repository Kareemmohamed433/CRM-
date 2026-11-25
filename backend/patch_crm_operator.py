import sys

def patch_file():
    with open("backend/app/services/crm_operator_service.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Add imports if not present
    if "from backend.app.services.conversation_state_manager import ConversationStateManager" not in content:
        import_marker = "logger = logging.getLogger(__name__)"
        new_imports = (
            "from backend.app.services.conversation_state_manager import ConversationStateManager\n"
            "from backend.app.services.ai_tools import ai_tool_registry\n\n"
            "logger = logging.getLogger(__name__)"
        )
        content = content.replace(import_marker, new_imports, 1)

    # 2. Add intent classifications in _classify_intent
    classify_marker = "        # 6. Task Summarization"
    new_classifications = """        # 5.5 Sales Summary & Reports
        if any(k in q for k in ["ملخص المبيعات", "ايرادات", "إيرادات", "ارقام المبيعات", "أرقام المبيعات", "تقرير المبيعات", "sales summary"]):
            return CRMOperationType.SALES_SUMMARY

        # 5.6 Team Performance
        if any(k in q for k in ["اداء الفريق", "أداء الفريق", "اداء المبيعات", "أداء المبيعات", "مؤشرات الفريق", "انجاز الفريق", "team performance"]):
            return CRMOperationType.TEAM_PERFORMANCE

        # 5.7 Customer Pipeline Stages
        if any(k in q for k in ["مراحل البيع", "خط الانابيب", "خط الأنابيب", "توزيع العملاء", "pipeline"]):
            return CRMOperationType.CUSTOMER_PIPELINE

        # 5.8 Customer History & Timeline
        if any(k in q for k in ["تاريخ العميل", "سجل العميل", "انشطة العميل", "أنشطة العميل", "مكالمات العميل", "تاريخ التواصل"]):
            return CRMOperationType.CUSTOMER_HISTORY

        # 5.9 Property Offer / WhatsApp Pitch
        if any(k in q for k in ["رسالة واتساب", "رساله واتساب", "عرض عقاري", "عرض سعر", "ابعت عرض", "تجهيز عرض", "property offer"]):
            return CRMOperationType.PROPERTY_OFFER

        # 6. Task Summarization"""
    if "CRMOperationType.SALES_SUMMARY" not in content:
        content = content.replace(classify_marker, new_classifications, 1)

    # 3. Add intent routing in process_turn
    routing_marker = "        # ---------------------------------------------------------------------\n        # 8. Handle SUMMARIZE_TASKS Operation\n        # ---------------------------------------------------------------------"
    new_routings = """        # ---------------------------------------------------------------------
        # 7.5 Handle SALES_SUMMARY Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.SALES_SUMMARY:
            tool_res = ai_tool_registry.execute("get_sales_summary", db, current_user, {"period": "month"})
            return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                reply=tool_res.message,
                reply_audio=tool_res.message,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.SALES_SUMMARY,
                execution_result=tool_res.data,
                suggested_tools_called=["get_sales_summary"]
            ))

        # ---------------------------------------------------------------------
        # 7.6 Handle TEAM_PERFORMANCE Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.TEAM_PERFORMANCE:
            tool_res = ai_tool_registry.execute("get_team_performance", db, current_user, {})
            return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                reply=tool_res.message,
                reply_audio=tool_res.message,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.TEAM_PERFORMANCE,
                execution_result=tool_res.data,
                suggested_tools_called=["get_team_performance"]
            ))

        # ---------------------------------------------------------------------
        # 7.7 Handle CUSTOMER_PIPELINE Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.CUSTOMER_PIPELINE:
            tool_res = ai_tool_registry.execute("get_customer_pipeline", db, current_user, {})
            return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                reply=tool_res.message,
                reply_audio=tool_res.message,
                conversation_state=ConversationState.IDLE,
                operation=CRMOperationType.CUSTOMER_PIPELINE,
                execution_result=tool_res.data,
                suggested_tools_called=["get_customer_pipeline"]
            ))

        # ---------------------------------------------------------------------
        # 7.8 Handle CUSTOMER_HISTORY Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.CUSTOMER_HISTORY:
            lead_res = resolve_person(q, db, current_user.company_id)
            lead_id = lead_res.get("lead_id") or ctx.get("lead_id")
            if lead_id:
                tool_res = ai_tool_registry.execute("get_customer_history", db, current_user, {"customer_id": lead_id})
                return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                    reply=tool_res.message,
                    reply_audio=tool_res.message,
                    conversation_state=ConversationState.IDLE,
                    operation=CRMOperationType.CUSTOMER_HISTORY,
                    execution_result={"timeline": tool_res.data},
                    suggested_tools_called=["get_customer_history"]
                ))
            else:
                return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                    reply="مين العميل اللي تحب أعرض لحضرتك سجله التاريخي؟",
                    reply_audio="مين العميل اللي تحب أعرض لحضرتك سجله التاريخي؟",
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=CRMOperationType.CUSTOMER_HISTORY,
                    missing_fields=["customer_id"]
                ))

        # ---------------------------------------------------------------------
        # 7.9 Handle PROPERTY_OFFER Operation
        # ---------------------------------------------------------------------
        if intent == CRMOperationType.PROPERTY_OFFER:
            lead_res = resolve_person(q, db, current_user.company_id)
            lead_id = lead_res.get("lead_id") or ctx.get("lead_id")
            prop_id = ctx.get("property_id")
            if lead_id and not prop_id:
                first_prop = db.query(Property).filter(Property.company_id == current_user.company_id).first()
                if first_prop:
                    prop_id = first_prop.id
            if lead_id and prop_id:
                tool_res = ai_tool_registry.execute("prepare_property_message", db, current_user, {"customer_id": lead_id, "property_id": prop_id})
                return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                    reply=tool_res.message,
                    reply_audio="تم تجهيز رسالة الواتساب للعميل بالمواصفات والسعر ونظام السداد.",
                    conversation_state=ConversationState.IDLE,
                    operation=CRMOperationType.PROPERTY_OFFER,
                    execution_result=tool_res.data,
                    suggested_tools_called=["prepare_property_message"]
                ))
            elif not lead_id:
                return self._finalize_turn(db, current_user, state_dto, CRMOperatorResult(
                    reply="تحب أجهز رسالة العرض لأي عميل؟",
                    reply_audio="تحب أجهز رسالة العرض لأي عميل؟",
                    conversation_state=ConversationState.COLLECTING_INFO,
                    operation=CRMOperationType.PROPERTY_OFFER,
                    missing_fields=["customer_id"]
                ))

        # ---------------------------------------------------------------------
        # 8. Handle SUMMARIZE_TASKS Operation
        # ---------------------------------------------------------------------"""
    if "CRMOperationType.SALES_SUMMARY" in content and "7.5 Handle SALES_SUMMARY" not in content:
        content = content.replace(routing_marker, new_routings, 1)

    # 4. Integrate ConversationStateManager in process_turn and add _finalize_turn helper
    start_turn_marker = """        ctx = dict(current_context or {})
        q = user_query.strip()
        q_lower = q.lower()"""

    new_start_turn = """        ctx = dict(current_context or {})
        q = user_query.strip()
        q_lower = q.lower()

        state_dto = ConversationStateManager.get_or_create_state(
            db, current_user,
            conversation_id=ctx.get("conversation_id"),
            legacy_context=ctx
        )
        # Merge persistent state into context if context lost
        for k, v in state_dto.collected_fields.items():
            if k not in ctx:
                ctx[k] = v"""
    if "state_dto = ConversationStateManager.get_or_create_state" not in content:
        content = content.replace(start_turn_marker, new_start_turn, 1)

    # Helper method _finalize_turn
    finalize_def = """    def _finalize_turn(
        self,
        db: Session,
        current_user: User,
        state_dto: Any,
        res: CRMOperatorResult
    ) -> CRMOperatorResult:
        try:
            state_dto.intent = res.operation.value if hasattr(res.operation, 'value') else str(res.operation)
            state_dto.missing_fields = res.missing_fields
            state_dto.confirmation_preview = res.confirmation_preview or {}
            if res.suggested_tools_called:
                state_dto.pending_tool = res.suggested_tools_called[0]
            for k, v in res.current_context.items():
                if k not in ("state", "operation", "missing_fields", "confirmation_preview"):
                    state_dto.collected_fields[k] = v
            ConversationStateManager.save_state(db, state_dto)
            res.current_context["conversation_id"] = state_dto.conversation_id
        except Exception as e:
            logger.warning(f"[CRMOperator] Failed syncing conversation state: {e}")
        return res
"""
    if "def _finalize_turn(" not in content:
        # insert right before process_turn
        proc_turn_marker = "    def process_turn("
        content = content.replace(proc_turn_marker, finalize_def + "\n" + proc_turn_marker, 1)

    with open("backend/app/services/crm_operator_service.py", "w", encoding="utf-8") as f:
        f.write(content)

    print("crm_operator_service.py patched successfully.")

if __name__ == "__main__":
    patch_file()

