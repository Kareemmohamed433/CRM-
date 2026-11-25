from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles
from backend.app.models.models import (
    LeadTransferRequest, Lead, User, UserRole, TransferStatus,
    LeadAssignmentHistory, Notification
)
from backend.app.schemas.transfer import (
    TransferRequestCreate, TransferReviewRequest, TransferRequestOut
)
from backend.app.services.audit_service import log_audit_event

router = APIRouter(prefix="/transfers", tags=["Lead Transfers & Reassignment"])


def format_transfer_out(t: LeadTransferRequest) -> TransferRequestOut:
    return TransferRequestOut(
        id=t.id,
        company_id=t.company_id,
        lead_id=t.lead_id,
        lead_name=t.lead.full_name if t.lead else "Unknown Lead",
        current_owner_id=t.current_owner_id,
        current_owner_name=t.current_owner.full_name if t.current_owner else "Unassigned",
        requested_owner_id=t.requested_owner_id,
        requested_owner_name=t.requested_owner.full_name if t.requested_owner else "Unknown Agent",
        requested_by_id=t.requested_by_id,
        requested_by_name=t.requested_by.full_name if t.requested_by else "Agent",
        reason=t.reason,
        notes=t.notes or "",
        status=t.status,
        reviewer_id=t.reviewer_id,
        reviewer_name=t.reviewer.full_name if t.reviewer else None,
        review_notes=t.review_notes or "",
        created_at=t.created_at,
        reviewed_at=t.reviewed_at,
    )


@router.get("", response_model=List[TransferRequestOut])
def list_transfer_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(LeadTransferRequest).filter(LeadTransferRequest.company_id == current_user.company_id)

    # Agents only see transfers they requested or where they are current/target owner
    if current_user.role == UserRole.SALES_AGENT:
        query = query.filter(
            (LeadTransferRequest.requested_by_id == current_user.id) |
            (LeadTransferRequest.current_owner_id == current_user.id) |
            (LeadTransferRequest.requested_owner_id == current_user.id)
        )

    transfers = query.order_by(LeadTransferRequest.created_at.desc()).all()
    return [format_transfer_out(t) for t in transfers]


@router.post("", response_model=TransferRequestOut)
def request_lead_transfer(
    req_in: TransferRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify lead in company
    lead = db.query(Lead).filter(Lead.id == req_in.lead_id, Lead.company_id == current_user.company_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Verify target agent in same company
    target_agent = db.query(User).filter(
        User.id == req_in.requested_owner_id,
        User.company_id == current_user.company_id,
        User.is_active == True
    ).first()
    if not target_agent:
        raise HTTPException(status_code=400, detail="Target agent not found or inactive in this company")

    if lead.assigned_agent_id == req_in.requested_owner_id:
        raise HTTPException(status_code=400, detail="Lead is already assigned to this agent")

    # Check pending request
    existing_pending = db.query(LeadTransferRequest).filter(
        LeadTransferRequest.lead_id == lead.id,
        LeadTransferRequest.status == TransferStatus.PENDING
    ).first()
    if existing_pending:
        raise HTTPException(
            status_code=400,
            detail="A transfer request for this lead is already pending review"
        )

    new_transfer = LeadTransferRequest(
        company_id=current_user.company_id,
        lead_id=lead.id,
        current_owner_id=lead.assigned_agent_id,
        requested_owner_id=req_in.requested_owner_id,
        requested_by_id=current_user.id,
        reason=req_in.reason,
        notes=req_in.notes or "",
        status=TransferStatus.PENDING
    )
    db.add(new_transfer)
    db.commit()
    db.refresh(new_transfer)

    # Notify managers about new transfer request
    managers = db.query(User).filter(
        User.company_id == current_user.company_id,
        User.role.in_([UserRole.SALES_MANAGER, UserRole.COMPANY_ADMIN])
    ).all()
    for m in managers:
        n = Notification(
            company_id=current_user.company_id,
            user_id=m.id,
            title="طلب نقل عميل جديد",
            message=f"طلب {current_user.full_name} نقل العميل {lead.full_name} إلى {target_agent.full_name}.",
            link="/transfers",
            notification_type="TRANSFER_REQUEST"
        )
        db.add(n)
    db.commit()

    return format_transfer_out(new_transfer)


@router.post("/{transfer_id}/review", response_model=TransferRequestOut)
def review_lead_transfer(
    transfer_id: int,
    review_in: TransferReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.TEAM_LEADER, UserRole.SUPER_ADMIN]))
):
    transfer = db.query(LeadTransferRequest).filter(
        LeadTransferRequest.id == transfer_id,
        LeadTransferRequest.company_id == current_user.company_id
    ).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer request not found")

    if transfer.status != TransferStatus.PENDING:
        raise HTTPException(status_code=400, detail="This transfer request has already been reviewed")

    transfer.reviewer_id = current_user.id
    transfer.review_notes = review_in.review_notes or ""
    transfer.reviewed_at = datetime.utcnow()

    lead = db.query(Lead).filter(Lead.id == transfer.lead_id).first()

    if review_in.approved:
        transfer.status = TransferStatus.APPROVED
        prev_agent_id = lead.assigned_agent_id
        
        # Atomic reassignment
        lead.assigned_agent_id = transfer.requested_owner_id
        if transfer.requested_owner and transfer.requested_owner.team_id:
            lead.team_id = transfer.requested_owner.team_id

        # Record assignment history (Preserves complete historical record)
        history_entry = LeadAssignmentHistory(
            company_id=current_user.company_id,
            lead_id=lead.id,
            previous_agent_id=prev_agent_id,
            new_agent_id=transfer.requested_owner_id,
            changed_by_id=current_user.id,
            reason=f"Approved transfer: {transfer.reason}"
        )
        db.add(history_entry)

        # Notify new owner
        notif_new = Notification(
            company_id=current_user.company_id,
            user_id=transfer.requested_owner_id,
            title="تم إسناد عميل جديد لك",
            message=f"تمت الموافقة على نقل العميل {lead.full_name} إليك.",
            link=f"/leads/{lead.id}",
            notification_type="LEAD_ASSIGNED"
        )
        db.add(notif_new)

        # Notify old owner
        if prev_agent_id:
            notif_old = Notification(
                company_id=current_user.company_id,
                user_id=prev_agent_id,
                title="تم تحويل العميل",
                message=f"تم تحويل العميل {lead.full_name} إلى {transfer.requested_owner.full_name}.",
                link="/transfers",
                notification_type="INFO"
            )
            db.add(notif_old)

        log_audit_event(
            db=db,
            company_id=current_user.company_id,
            action="TRANSFER_LEAD_APPROVED",
            entity_type="Lead",
            entity_id=lead.id,
            actor_id=current_user.id,
            before_state={"assigned_agent_id": prev_agent_id},
            after_state={"assigned_agent_id": transfer.requested_owner_id}
        )
    else:
        transfer.status = TransferStatus.REJECTED

    db.commit()
    db.refresh(transfer)
    return format_transfer_out(transfer)
