from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal, Base, engine
from backend.app.core.security import get_password_hash
from backend.app.models.models import (
    Company, User, Team, Project, Property, Lead, Activity, FollowUp,
    Appointment, LeadTransferRequest, Notification, UserRole, PipelineStage,
    PriorityLevel, PropertyStatus, ActivityType, FollowUpStatus, TransferStatus,
    AppointmentStatus, SalesAgentProfile, Conversation, ConversationMessage, VoiceMetric,
    ConversationChannel, ConversationStatus, MessageSenderType, MessageType
)
from backend.app.services.scoring_service import calculate_lead_score


def seed_database():
    # Create all tables if not exist
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        # Check if already seeded
        if db.query(Company).first():
            print("Database already contains data. Skipping seed.")
            return

        print("Seeding initial data...")
        default_pwd = get_password_hash("Password123!")

        # 1. Companies
        company_a = Company(
            name="Nexora Developments & Brokerage",
            domain="nexora.com",
            settings={"currency": "EGP", "default_language": "ar", "auto_assign": True}
        )
        company_b = Company(
            name="Horizon Capital Real Estate",
            domain="horizon.com",
            settings={"currency": "EGP", "default_language": "en"}
        )
        db.add_all([company_a, company_b])
        db.flush()

        # 2. Users for Company A
        super_admin = User(
            company_id=company_a.id,
            email="superadmin@nexora.com",
            hashed_password=default_pwd,
            full_name="Tarek El-Masry (Super Admin)",
            phone="+201001112222",
            role=UserRole.SUPER_ADMIN,
            is_active=True
        )
        admin_a = User(
            company_id=company_a.id,
            email="admin@nexora.com",
            hashed_password=default_pwd,
            full_name="Karim Mansour (Company Admin)",
            phone="+201003334444",
            role=UserRole.COMPANY_ADMIN,
            is_active=True
        )
        manager_a = User(
            company_id=company_a.id,
            email="manager@nexora.com",
            hashed_password=default_pwd,
            full_name="Dalia Fouad (Sales Manager)",
            phone="+201005556666",
            role=UserRole.SALES_MANAGER,
            is_active=True
        )
        leader_a = User(
            company_id=company_a.id,
            email="leader@nexora.com",
            hashed_password=default_pwd,
            full_name="Sherif Nabil (Team Leader)",
            phone="+201007778888",
            role=UserRole.TEAM_LEADER,
            is_active=True
        )
        agent_1 = User(
            company_id=company_a.id,
            email="agent1@nexora.com",
            hashed_password=default_pwd,
            full_name="Ahmed Samir (Senior Consultant)",
            phone="+201009990001",
            role=UserRole.SALES_AGENT,
            is_active=True
        )
        agent_2 = User(
            company_id=company_a.id,
            email="agent2@nexora.com",
            hashed_password=default_pwd,
            full_name="Nour El-Din (Sales Agent)",
            phone="+201009990002",
            role=UserRole.SALES_AGENT,
            is_active=True
        )

        # Users for Company B (Tenant Isolation testing)
        admin_b = User(
            company_id=company_b.id,
            email="admin@horizon.com",
            hashed_password=default_pwd,
            full_name="Youssef Helmy (Horizon Admin)",
            phone="+201112223333",
            role=UserRole.COMPANY_ADMIN,
            is_active=True
        )
        agent_b = User(
            company_id=company_b.id,
            email="agent@horizon.com",
            hashed_password=default_pwd,
            full_name="Mariam Zaki (Horizon Agent)",
            phone="+201114445555",
            role=UserRole.SALES_AGENT,
            is_active=True
        )

        db.add_all([super_admin, admin_a, manager_a, leader_a, agent_1, agent_2, admin_b, agent_b])
        db.flush()

        # 3. Teams
        team_east = Team(
            company_id=company_a.id,
            name="New Cairo Elite Team",
            leader_id=leader_a.id
        )
        team_west = Team(
            company_id=company_a.id,
            name="Sheikh Zayed Luxury Team",
            leader_id=leader_a.id
        )
        db.add_all([team_east, team_west])
        db.flush()

        # Assign team to agents
        leader_a.team_id = team_east.id
        agent_1.team_id = team_east.id
        agent_2.team_id = team_west.id
        db.flush()

        # 4. Projects
        proj_crest = Project(
            company_id=company_a.id,
            name="The Crest New Cairo",
            developer="Il Cazar Developments",
            location="South Academy, New Cairo",
            description="Luxury master-planned community with clubhouse, crystal lagoons, and verdant landscapes.",
            project_type="Residential Compound",
            status="Launching"
        )
        proj_skyline = Project(
            company_id=company_a.id,
            name="Villette Heights",
            developer="Sodic",
            location="Golden Square, New Cairo",
            description="Signature apartments and sky villas with hotel-serviced amenities.",
            project_type="Residential",
            status="Under Construction"
        )
        proj_zayed = Project(
            company_id=company_a.id,
            name="Karmell New Zayed",
            developer="Sodic",
            location="New Zayed",
            description="Modern Californian architectural residential community.",
            project_type="Mixed-use",
            status="Under Construction"
        )
        # Horizon Project (Company B)
        proj_horizon = Project(
            company_id=company_b.id,
            name="Horizon Marina Palms",
            developer="Horizon Developments",
            location="North Coast",
            description="Exclusive seaside residences.",
            project_type="Resort",
            status="Ready to move"
        )
        db.add_all([proj_crest, proj_skyline, proj_zayed, proj_horizon])
        db.flush()

        # 5. Properties Inventory
        prop1 = Property(
            company_id=company_a.id,
            project_id=proj_crest.id,
            unit_number="C-104",
            property_type="Apartment",
            city="Cairo",
            location="New Cairo",
            area=145.0,
            bedrooms=2,
            bathrooms=2,
            floor=1,
            view="Clubhouse & Lagoon",
            finishing_status="Fully Finished with ACs",
            delivery_date="2026-12-31",
            total_price=3_850_000.0,
            currency="EGP",
            down_payment=385_000.0,
            installment_plan="8 Years Equal Installments",
            availability_status=PropertyStatus.AVAILABLE,
            description="Spacious 2-bedroom unit with direct lagoon view and private parking."
        )
        prop2 = Property(
            company_id=company_a.id,
            project_id=proj_crest.id,
            unit_number="C-302",
            property_type="Apartment",
            city="Cairo",
            location="New Cairo",
            area=175.0,
            bedrooms=3,
            bathrooms=3,
            floor=3,
            view="Central Park",
            finishing_status="Semi-Finished",
            delivery_date="2026-06-30",
            total_price=4_450_000.0,
            currency="EGP",
            down_payment=445_000.0,
            installment_plan="7 Years Equal",
            availability_status=PropertyStatus.AVAILABLE,
            description="Corner 3-bedroom apartment with generous terrace."
        )
        prop3 = Property(
            company_id=company_a.id,
            project_id=proj_skyline.id,
            unit_number="V-501",
            property_type="Sky Villa",
            city="Cairo",
            location="New Cairo",
            area=240.0,
            bedrooms=4,
            bathrooms=4,
            floor=5,
            view="Open Landscape",
            finishing_status="Core & Shell",
            delivery_date="2027-03-31",
            total_price=7_200_000.0,
            currency="EGP",
            down_payment=720_000.0,
            installment_plan="9 Years",
            availability_status=PropertyStatus.AVAILABLE,
            description="Penthouse sky villa with private rooftop jacuzzi."
        )
        prop4 = Property(
            company_id=company_a.id,
            project_id=proj_zayed.id,
            unit_number="KZ-12",
            property_type="Townhouse",
            city="Giza",
            location="Sheikh Zayed",
            area=210.0,
            bedrooms=3,
            bathrooms=3,
            floor=0,
            view="Private Garden",
            finishing_status="Fully Finished",
            delivery_date="2026-09-30",
            total_price=5_900_000.0,
            currency="EGP",
            down_payment=600_000.0,
            installment_plan="8 Years Equal",
            availability_status=PropertyStatus.RESERVED,
            description="Modern townhouse with 80sqm private landscaped garden."
        )
        # Horizon property
        prop_horizon = Property(
            company_id=company_b.id,
            project_id=proj_horizon.id,
            unit_number="H-101",
            property_type="Chalet",
            city="North Coast",
            location="Ras El Hekma",
            area=120.0,
            bedrooms=2,
            bathrooms=2,
            floor=1,
            view="Direct Sea View",
            finishing_status="Ultra Super Lux",
            delivery_date="2025-06-01",
            total_price=6_500_000.0,
            currency="EGP",
            down_payment=1_000_000.0,
            installment_plan="5 Years",
            availability_status=PropertyStatus.AVAILABLE,
            description="Luxury chalet overlooking crystal turquoise beach."
        )
        db.add_all([prop1, prop2, prop3, prop4, prop_horizon])
        db.flush()

        # 6. Leads
        now = datetime.utcnow()
        lead1 = Lead(
            company_id=company_a.id,
            full_name="Ahmed Mahmoud",
            phone="+201012345678",
            email="ahmed.mahmoud@gmail.com",
            preferred_contact_method="WhatsApp",
            source="Meta Ads",
            team_id=team_east.id,
            assigned_agent_id=agent_1.id,
            pipeline_stage=PipelineStage.VISIT_COMPLETED,
            budget_min=3_000_000.0,
            budget_max=4_000_000.0,
            preferred_project_id=proj_crest.id,
            preferred_location="New Cairo / التجمع",
            property_type="Apartment",
            bedrooms=2,
            down_payment_budget=400_000.0,
            purchase_timeline="Immediate (1 month)",
            notes="عاين وحدة C-302 ورفض السعر لأنها أعلى من 4 مليون. مهتم ببديل في التجمع أقل من 4 مليون.",
            tags="Serious, Hot, New Cairo",
            last_contact_date=now - timedelta(hours=3),
            next_followup_date=now + timedelta(days=1),
            priority=PriorityLevel.URGENT,
            score=88
        )
        lead2 = Lead(
            company_id=company_a.id,
            full_name="Dr. Tamer Mostafa",
            phone="+201098765432",
            email="dr.tamer@yahoo.com",
            preferred_contact_method="Phone",
            source="Referral",
            team_id=team_east.id,
            assigned_agent_id=agent_1.id,
            pipeline_stage=PipelineStage.QUALIFIED,
            budget_min=6_000_000.0,
            budget_max=8_000_000.0,
            preferred_project_id=proj_skyline.id,
            preferred_location="New Cairo",
            property_type="Sky Villa",
            bedrooms=4,
            down_payment_budget=800_000.0,
            purchase_timeline="1-3 months",
            notes="Interested in spacious family sky villa with clubhouse access.",
            tags="VIP, Cash Down",
            last_contact_date=now - timedelta(days=2),
            next_followup_date=now - timedelta(hours=4),  # Overdue!
            priority=PriorityLevel.HIGH,
            score=78
        )
        lead3 = Lead(
            company_id=company_a.id,
            full_name="Eng. Yasser Soliman",
            phone="+201055512345",
            email="yasser.soliman@techcorp.eg",
            preferred_contact_method="WhatsApp",
            source="Google Search",
            team_id=team_west.id,
            assigned_agent_id=agent_2.id,
            pipeline_stage=PipelineStage.VISIT_SCHEDULED,
            budget_min=5_000_000.0,
            budget_max=6_500_000.0,
            preferred_project_id=proj_zayed.id,
            preferred_location="Sheikh Zayed",
            property_type="Townhouse",
            bedrooms=3,
            down_payment_budget=600_000.0,
            purchase_timeline="Immediate (1 month)",
            notes="Requested site visit for Karmell townhouse this week.",
            tags="Zayed, Ready Down",
            last_contact_date=now - timedelta(days=1),
            next_followup_date=now,  # Due today
            priority=PriorityLevel.URGENT,
            score=92
        )
        lead4 = Lead(
            company_id=company_a.id,
            full_name="Mona El-Shazly",
            phone="+201033399988",
            email="mona.shazly@outlook.com",
            preferred_contact_method="WhatsApp",
            source="TikTok Ads",
            team_id=team_east.id,
            assigned_agent_id=agent_1.id,
            pipeline_stage=PipelineStage.NEW,
            budget_min=2_500_000.0,
            budget_max=3_500_000.0,
            preferred_location="New Cairo",
            property_type="Apartment",
            purchase_timeline="6 months+",
            notes="New incoming lead, no follow-up scheduled yet.",
            tags="Fresh",
            next_followup_date=None,  # Stalled / No Next Action
            priority=PriorityLevel.MEDIUM,
            score=45
        )
        # Horizon lead (Company B)
        lead_horizon = Lead(
            company_id=company_b.id,
            full_name="Khaled Barakat",
            phone="+201200001111",
            email="khaled@horizonclient.com",
            preferred_contact_method="Phone",
            source="Exhibition",
            assigned_agent_id=agent_b.id,
            pipeline_stage=PipelineStage.CONTACTED,
            budget_min=5_000_000.0,
            budget_max=7_000_000.0,
            preferred_location="North Coast",
            property_type="Chalet",
            purchase_timeline="Immediate (1 month)",
            notes="Company B client. Must NEVER leak to Company A.",
            priority=PriorityLevel.HIGH,
            score=70
        )
        db.add_all([lead1, lead2, lead3, lead4, lead_horizon])
        db.flush()

        # Update explainable score factors
        for l in [lead1, lead2, lead3, lead4, lead_horizon]:
            s, factors, prio = calculate_lead_score(l)
            l.score = s
            l.score_factors = factors
            l.priority = prio

        # 7. Activities
        act1 = Activity(
            company_id=company_a.id,
            lead_id=lead1.id,
            property_id=prop2.id,
            user_id=agent_1.id,
            activity_type=ActivityType.VISIT,
            summary="أنا نزلت مع أحمد النهارده عاينّا شقة في التجمع، بس هو مش مقتنع بالسعر، وعايز حاجة أقل من أربعة مليون، وقال هيفكر ويرد عليا.",
            outcome="Completed - Price Objection",
            objection="Price too high / السعر مرتفع (> 4M)",
            sentiment="Hesitant",
            next_action="عرض شقة C-104 البديلة بسعر 3,850,000 ج",
            next_followup_date=now + timedelta(days=1),
            created_at=now - timedelta(hours=3)
        )
        act2 = Activity(
            company_id=company_a.id,
            lead_id=lead2.id,
            property_id=prop3.id,
            user_id=agent_1.id,
            activity_type=ActivityType.CALL,
            summary="Detailed 15 min phone consultation discussing Skyline sky villa floor plans and installment frequency.",
            outcome="Positive Interest",
            objection="",
            sentiment="Positive",
            next_action="Send updated payment breakdown via WhatsApp",
            created_at=now - timedelta(days=2)
        )
        db.add_all([act1, act2])

        # 8. Follow-ups
        f_overdue = FollowUp(
            company_id=company_a.id,
            lead_id=lead2.id,
            assigned_user_id=agent_1.id,
            team_id=team_east.id,
            follow_up_type="WhatsApp",
            purpose="Send payment schedule for Villette Heights Sky Villa",
            due_date=now - timedelta(hours=4),
            priority=PriorityLevel.HIGH,
            status=FollowUpStatus.OVERDUE,
            notes="Client is waiting for the customized 9-year schedule."
        )
        f_today = FollowUp(
            company_id=company_a.id,
            lead_id=lead3.id,
            assigned_user_id=agent_2.id,
            team_id=team_west.id,
            follow_up_type="Call",
            purpose="Confirm site visit timing for Karmell Townhouse",
            due_date=now + timedelta(hours=2),
            priority=PriorityLevel.URGENT,
            status=FollowUpStatus.DUE_TODAY,
            notes="Check if client prefers morning 11 AM or afternoon 2 PM."
        )
        f_upcoming = FollowUp(
            company_id=company_a.id,
            lead_id=lead1.id,
            assigned_user_id=agent_1.id,
            team_id=team_east.id,
            follow_up_type="Call",
            purpose="Present alternative unit C-104 (3.85M) to Ahmed Mahmoud",
            due_date=now + timedelta(days=1),
            priority=PriorityLevel.HIGH,
            status=FollowUpStatus.PENDING,
            notes="Explain that C-104 is fully finished and within the 4M ceiling."
        )
        db.add_all([f_overdue, f_today, f_upcoming])

        # 9. Appointment
        app1 = Appointment(
            company_id=company_a.id,
            lead_id=lead3.id,
            property_id=prop4.id,
            user_id=agent_2.id,
            title="Site Visit with Eng. Yasser Soliman",
            appointment_type="Property Visit",
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=4),
            location="Karmell Sales Center, New Zayed",
            notes="Client bringing family to review the unit layout."
        )
        db.add(app1)

        # 10. Sample Transfer Request (Agent 2 requesting transfer to Agent 1 because client wants New Cairo)
        tr1 = LeadTransferRequest(
            company_id=company_a.id,
            lead_id=lead1.id,
            current_owner_id=agent_2.id,
            requested_owner_id=agent_1.id,
            requested_by_id=agent_2.id,
            reason="Project Specialization",
            notes="Customer strictly wants New Cairo; Ahmed Samir specializes in The Crest project.",
            status=TransferStatus.APPROVED,
            reviewer_id=manager_a.id,
            review_notes="Approved. Reassigned to New Cairo specialist.",
            created_at=now - timedelta(days=1),
            reviewed_at=now - timedelta(hours=20)
        )
        db.add(tr1)

        # 11. Sample Notifications
        notif1 = Notification(
            company_id=company_a.id,
            user_id=agent_1.id,
            title="Lead Transferred to You",
            message="Lead Ahmed Mahmoud was transferred to your pipeline by Manager Dalia Fouad.",
            link=f"/leads/{lead1.id}",
            notification_type="LEAD_ASSIGNED",
            is_read=False
        )
        notif2 = Notification(
            company_id=company_a.id,
            user_id=agent_1.id,
            title="Overdue Follow-up Alert",
            message="Follow-up with Dr. Tamer Mostafa is overdue by 4 hours.",
            link="/followups",
            notification_type="OVERDUE_TASK",
            is_read=False
        )
        db.add_all([notif1, notif2])

        # 12. Sales Agent Profiles
        prof_agent1 = SalesAgentProfile(
            user_id=agent_1.id,
            company_id=company_a.id,
            personality_prompt="أحمد سمير: مستشار عقاري أول متخصص في التجمع الخامس، ودود واحترافي، يتحدث باللهجة المصرية الطبيعية.",
            preferred_voice="ar-EG-SalmaNeural",
            speaking_rate="+20%",
            working_hours_start="09:00",
            working_hours_end="18:00",
            max_active_leads=60,
            is_accepting_leads=True,
            monthly_target_sales=15000000.0,
            target_visits_per_month=25
        )
        prof_agent2 = SalesAgentProfile(
            user_id=agent_2.id,
            company_id=company_a.id,
            personality_prompt="نور الدين: مستشار عقاري متخصص في الشيخ زايد وأكتوبر، هادئ ومقنع، يقدم شروحات مفصلة لخطط السداد.",
            preferred_voice="ar-EG-ShakirNeural",
            speaking_rate="+15%",
            working_hours_start="09:00",
            working_hours_end="18:00",
            max_active_leads=45,
            is_accepting_leads=True,
            monthly_target_sales=12000000.0,
            target_visits_per_month=20
        )
        db.add_all([prof_agent1, prof_agent2])

        # 13. Omnichannel Conversations
        conv1 = Conversation(
            company_id=company_a.id,
            lead_id=lead1.id,
            assigned_agent_id=agent_1.id,
            team_id=team_east.id,
            channel=ConversationChannel.WHATSAPP,
            status=ConversationStatus.OPEN,
            customer_name=lead1.full_name,
            customer_phone=lead1.phone,
            customer_identifier="201011122233@c.us",
            unread_count=1,
            ai_enabled=True,
            human_takeover=False,
            last_message_text="مساء الخير، كنت بستفسر عن الوحدة البديلة C-104 في The Crest وطريقة التقسيط؟",
            last_message_time=now - timedelta(minutes=15),
            ai_summary="استفسار عن الوحدة C-104 البديلة بميزانية أقل من 4 مليون ونظام الأقساط.",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(minutes=15)
        )
        db.add(conv1)
        db.flush()

        msg1_1 = ConversationMessage(
            conversation_id=conv1.id,
            company_id=company_a.id,
            sender_type=MessageSenderType.CUSTOMER,
            message_type=MessageType.TEXT,
            content="أهلاً يا باشا، أنا شفت شقة The Crest معاك من يومين وعايز أعرف تفاصيل أكتر.",
            created_at=now - timedelta(days=1)
        )
        msg1_2 = ConversationMessage(
            conversation_id=conv1.id,
            company_id=company_a.id,
            sender_type=MessageSenderType.AGENT,
            sender_id=agent_1.id,
            message_type=MessageType.TEXT,
            content="أهلاً بحضرتك يا أستاذ أحمد! تحت أمرك، عندنا الوحدة C-104 بمساحة 145م2 تشطيب كامل وسعرها 3.85 مليون ومقدم 10%.",
            created_at=now - timedelta(hours=18)
        )
        msg1_3 = ConversationMessage(
            conversation_id=conv1.id,
            company_id=company_a.id,
            sender_type=MessageSenderType.CUSTOMER,
            message_type=MessageType.TEXT,
            content="مساء الخير، كنت بستفسر عن الوحدة البديلة C-104 في The Crest وطريقة التقسيط؟",
            created_at=now - timedelta(minutes=15)
        )
        db.add_all([msg1_1, msg1_2, msg1_3])

        # 14. Voice Metrics Telemetry Seed
        vm1 = VoiceMetric(
            company_id=company_a.id,
            user_id=agent_1.id,
            stage="STT",
            provider="groq-whisper",
            duration_ms=280.0,
            success=True,
            created_at=now - timedelta(hours=2)
        )
        vm2 = VoiceMetric(
            company_id=company_a.id,
            user_id=agent_1.id,
            stage="LLM",
            provider="qwen-chat",
            duration_ms=450.0,
            success=True,
            tokens_used=145,
            created_at=now - timedelta(hours=2)
        )
        vm3 = VoiceMetric(
            company_id=company_a.id,
            user_id=agent_1.id,
            stage="TTS",
            provider="edge-tts",
            duration_ms=380.0,
            success=True,
            created_at=now - timedelta(hours=2)
        )
        db.add_all([vm1, vm2, vm3])

        db.commit()
        print("Database seeded successfully with companies, users, properties, leads, and activities!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
