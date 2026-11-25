"""
Comprehensive tests for Unified Property & Location Management and AI Integration:
- Independent properties without project (project_id=None)
- Geographic hierarchy integration (Governorate -> Area/City -> Project -> Properties)
- Property videos (file upload and external URL)
- Soft-delete & archiving
- AI Inventory tools (search_available_properties, get_location_inventory, compare_properties, get_property_media, get_property_recommendations)
- Conversational Egyptian Arabic multi-turn filter preservation across turns
"""

import pytest
from datetime import datetime
from backend.app.models.models import (
    User, UserRole, Company, Property, Project, Governorate, City, District,
    PropertyStatus, PropertyVideo, PropertyImage
)
from backend.app.services.ai_tools import ai_tool_registry
from backend.app.services.crm_operator_service import get_crm_operator
from backend.app.schemas.crm_actions import CRMOperationType


@pytest.fixture
def property_test_setup(db_session):
    # Company
    comp = db_session.query(Company).filter(Company.id == 1).first()
    if not comp:
        comp = Company(id=1, name="Nexora Test Real Estate")
        db_session.add(comp)
        db_session.commit()

    # User
    agent = db_session.query(User).filter(User.email == "prop_agent_test@nexora.com").first()
    if not agent:
        agent = User(
            email="prop_agent_test@nexora.com",
            hashed_password="hash",
            full_name="Tamer Sales",
            role=UserRole.SALES_AGENT,
            company_id=comp.id,
            is_active=True
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

    # Locations
    gov = db_session.query(Governorate).filter(Governorate.name_ar == "القاهرة").first()
    if not gov:
        gov = Governorate(name_ar="القاهرة", name_en="Cairo", is_active=True)
        db_session.add(gov)
        db_session.commit()
        db_session.refresh(gov)

    city = db_session.query(City).filter(City.name_ar == "القاهرة الجديدة", City.governorate_id == gov.id).first()
    if not city:
        city = City(governorate_id=gov.id, name_ar="القاهرة الجديدة", name_en="New Cairo", is_active=True)
        db_session.add(city)
        db_session.commit()
        db_session.refresh(city)

    # Project
    proj = db_session.query(Project).filter(Project.name == "كمبوند النرجس ريزيدنس", Project.company_id == comp.id).first()
    if not proj:
        proj = Project(
            company_id=comp.id,
            name="كمبوند النرجس ريزيدنس",
            developer="إعمار المستقبل",
            location="التجمع الخامس",
            governorate_id=gov.id,
            city_id=city.id,
            project_type="Residential",
            status="Under Construction"
        )
        db_session.add(proj)
        db_session.commit()
        db_session.refresh(proj)

    # Property 1 in Project (3 bedrooms, 3.2M)
    p1 = db_session.query(Property).filter(Property.unit_number == "NR-301", Property.company_id == comp.id).first()
    if not p1:
        p1 = Property(
            company_id=comp.id,
            project_id=proj.id,
            title="شقة 3 غرف في النرجس",
            unit_number="NR-301",
            property_type="Apartment",
            city="القاهرة",
            location="التجمع الخامس",
            governorate_id=gov.id,
            city_id=city.id,
            area=150.0,
            bedrooms=3,
            bathrooms=2,
            floor=3,
            view="Garden",
            finishing_status="Fully Finished",
            delivery_date="2027-06-30",
            total_price=3_200_000.0,
            currency="EGP",
            down_payment=320_000.0,
            installment_plan="7 Years Equal",
            availability_status=PropertyStatus.AVAILABLE,
            is_archived=False
        )
        db_session.add(p1)
        db_session.commit()
        db_session.refresh(p1)

    # Property 2 in Project (4 bedrooms, 3.8M)
    p2 = db_session.query(Property).filter(Property.unit_number == "NR-402", Property.company_id == comp.id).first()
    if not p2:
        p2 = Property(
            company_id=comp.id,
            project_id=proj.id,
            title="شقة 4 غرف في النرجس",
            unit_number="NR-402",
            property_type="Apartment",
            city="القاهرة",
            location="التجمع الخامس",
            governorate_id=gov.id,
            city_id=city.id,
            area=210.0,
            bedrooms=4,
            bathrooms=3,
            floor=4,
            view="Pool & Landscape",
            finishing_status="Ultra Super Lux",
            delivery_date="2026-12-31",
            total_price=3_800_000.0,
            currency="EGP",
            down_payment=400_000.0,
            installment_plan="8 Years Equal",
            availability_status=PropertyStatus.AVAILABLE,
            is_archived=False
        )
        db_session.add(p2)
        db_session.commit()
        db_session.refresh(p2)

    # Property 3: Independent Property without Project (project_id=None)
    p3 = db_session.query(Property).filter(Property.unit_number == "IND-105", Property.company_id == comp.id).first()
    if not p3:
        p3 = Property(
            company_id=comp.id,
            project_id=None,
            title="شقة مستقلة بالتجمع الخامس",
            unit_number="IND-105",
            property_type="Apartment",
            city="القاهرة",
            location="التجمع الخامس",
            governorate_id=gov.id,
            city_id=city.id,
            area=175.0,
            bedrooms=3,
            bathrooms=2,
            floor=2,
            view="Open Street",
            finishing_status="Core & Shell",
            delivery_date="Immediate",
            total_price=2_700_000.0,
            currency="EGP",
            down_payment=500_000.0,
            installment_plan="Cash or 3 Years",
            availability_status=PropertyStatus.AVAILABLE,
            is_archived=False
        )
        db_session.add(p3)
        db_session.commit()
        db_session.refresh(p3)
    else:
        p3.is_archived = False
        p3.availability_status = PropertyStatus.AVAILABLE
        db_session.commit()

    return {
        "company": comp,
        "agent": agent,
        "governorate": gov,
        "city": city,
        "project": proj,
        "p1": p1,
        "p2": p2,
        "p3": p3
    }


def test_independent_property_and_archiving(db_session, property_test_setup):
    """Verifies that properties can exist without a project and can be archived/soft-deleted."""
    setup = property_test_setup
    p3 = setup["p3"]
    assert p3.project_id is None
    assert p3.is_archived is False
    assert p3.availability_status == PropertyStatus.AVAILABLE

    # Archive unit
    p3.is_archived = True
    p3.availability_status = PropertyStatus.ARCHIVED
    db_session.commit()
    db_session.refresh(p3)
    assert p3.is_archived is True

    # Search excludes archived by default
    res = ai_tool_registry.execute_tool(
        "search_available_properties", db_session, setup["agent"],
        {"location": "التجمع الخامس", "include_archived": False}
    )
    assert res.success is True
    ids = [item["id"] for item in res.data]
    assert p3.id not in ids

    # Unarchive
    p3.is_archived = False
    p3.availability_status = PropertyStatus.AVAILABLE
    db_session.commit()


def test_property_videos_and_media(db_session, property_test_setup):
    """Verifies property video management and media tools."""
    setup = property_test_setup
    p1 = setup["p1"]

    # Add external YouTube video
    vid = PropertyVideo(
        company_id=setup["company"].id,
        property_id=p1.id,
        video_url="https://www.youtube.com/watch?v=sample123",
        video_type="EXTERNAL",
        title="جولة داخل الوحدة 301",
        sort_order=1
    )
    db_session.add(vid)
    db_session.commit()

    # Tool get_property_media
    res = ai_tool_registry.execute_tool(
        "get_property_media", db_session, setup["agent"], {"property_id": p1.id}
    )
    assert res.success is True
    assert len(res.data["videos"]) >= 1
    assert res.data["videos"][0]["url"] == "https://www.youtube.com/watch?v=sample123"
    assert "جولة داخل الوحدة 301" in res.message


def test_location_inventory_and_compare_tools(db_session, property_test_setup):
    """Verifies get_location_inventory and compare_properties tools."""
    setup = property_test_setup
    p1 = setup["p1"]
    p2 = setup["p2"]

    # 1. Location inventory
    inv_res = ai_tool_registry.execute_tool(
        "get_location_inventory", db_session, setup["agent"], {"location": "التجمع الخامس"}
    )
    assert inv_res.success is True
    assert inv_res.data["available_units"] >= 2
    assert "مخزون الوحدات في التجمع الخامس" in inv_res.message

    # 2. Compare properties
    comp_res = ai_tool_registry.execute_tool(
        "compare_properties", db_session, setup["agent"], {"property_ids": [p1.id, p2.id]}
    )
    assert comp_res.success is True
    assert "مقارنة تفصيلية بين الوحدات" in comp_res.message
    assert comp_res.data["cheapest_id"] == p1.id
    assert comp_res.data["largest_id"] == p2.id


def test_conversational_multi_turn_filter_preservation(db_session, property_test_setup):
    """
    Tests full multi-turn conversational Egyptian Arabic scenario:
    Turn 1: 'عندنا شقق في القاهرة؟'
    Turn 2: 'التجمع الخامس' -> keeps القاهرة & شقق
    Turn 3: 'لحد 4 مليون وتكون 3 غرف' -> keeps previous + max_price 4M + 3 bedrooms
    Turn 4: 'خليها 4 غرف' -> updates bedrooms to 4, preserves القاهرة, التجمع, max_price 4M
    Turn 5: 'وريني الأرخص' -> preserves filters, sorts by price
    Turn 6: 'عندكم فيديو ليها؟' -> queries media of the last shown unit
    Turn 7: 'قارنلي بين الاتنين' -> compares the top 2 units
    Turn 8: 'عندنا كام شقة في التجمع؟' -> gives location inventory stats
    """
    setup = property_test_setup
    agent = setup["agent"]
    operator = get_crm_operator()

    conv_id = f"test_prop_conv_{agent.id}_{int(datetime.utcnow().timestamp())}"
    ctx = {"conversation_id": conv_id}

    # Turn 1: Search in Cairo
    res1 = operator.process_turn(db_session, agent, "عندنا شقق في القاهرة؟", current_context=ctx)
    assert res1.operation == CRMOperationType.SEARCH_PROPERTIES
    assert res1.current_context.get("property_filters", {}).get("governorate") == "القاهرة"
    assert res1.current_context.get("property_filters", {}).get("property_type") == "Apartment"
    ctx = res1.current_context

    # Turn 2: Narrow to New Cairo (التجمع الخامس)
    res2 = operator.process_turn(db_session, agent, "التجمع الخامس", current_context=ctx)
    assert res2.operation == CRMOperationType.SEARCH_PROPERTIES
    filters2 = res2.current_context.get("property_filters", {})
    assert filters2.get("governorate") == "القاهرة"
    assert filters2.get("location") == "التجمع الخامس"
    assert filters2.get("property_type") == "Apartment"
    ctx = res2.current_context

    # Turn 3: Add budget and bedrooms
    res3 = operator.process_turn(db_session, agent, "لحد 4 مليون وتكون غرفتين", current_context=ctx)
    assert res3.operation == CRMOperationType.SEARCH_PROPERTIES
    filters3 = res3.current_context.get("property_filters", {})
    assert filters3.get("location") == "التجمع الخامس"
    assert filters3.get("max_price") == 4_000_000.0
    assert filters3.get("bedrooms") == 2
    ctx = res3.current_context

    # Turn 4: Update bedrooms ("خليها 3 غرف")
    res4 = operator.process_turn(db_session, agent, "خليها 3 غرف", current_context=ctx)
    assert res4.operation == CRMOperationType.SEARCH_PROPERTIES
    filters4 = res4.current_context.get("property_filters", {})
    assert filters4.get("location") == "التجمع الخامس"
    assert filters4.get("max_price") == 4_000_000.0
    assert filters4.get("bedrooms") == 3  # Updated!
    ctx = res4.current_context

    # Turn 5: Sorting ("وريني الأرخص")
    res5 = operator.process_turn(db_session, agent, "وريني الأرخص", current_context=ctx)
    assert res5.operation == CRMOperationType.SEARCH_PROPERTIES
    assert res5.current_context.get("property_filters", {}).get("sort_by") == "price_asc"
    ctx = res5.current_context

    # Turn 6: Media request ("عندكم فيديو ليها؟")
    res6 = operator.process_turn(db_session, agent, "عندكم فيديو ليها؟", current_context=ctx)
    assert res6.operation == CRMOperationType.SEARCH_PROPERTIES
    assert "وسائط" in res6.reply or "فيديو" in res6.reply
    ctx = res6.current_context

    # Turn 7: Comparison ("قارنلي بين الاتنين")
    res7 = operator.process_turn(db_session, agent, "قارنلي بين الاتنين", current_context=ctx)
    assert res7.operation == CRMOperationType.SEARCH_PROPERTIES
    assert "مقارنة" in res7.reply
    ctx = res7.current_context

    # Turn 8: Inventory count ("عندنا كام شقة في التجمع؟")
    res8 = operator.process_turn(db_session, agent, "عندنا كام شقة في التجمع؟", current_context=ctx)
    assert res8.operation == CRMOperationType.SEARCH_PROPERTIES
    assert "مخزون" in res8.reply or "المتاح" in res8.reply
