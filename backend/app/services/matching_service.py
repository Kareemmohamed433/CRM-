from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models.models import Property, PropertyStatus, Lead


def find_alternative_properties(
    db: Session,
    company_id: int,
    max_price: Optional[float] = None,
    preferred_location: Optional[str] = None,
    property_type: Optional[str] = None,
    bedrooms: Optional[int] = None,
    max_down_payment: Optional[float] = None,
    exclude_property_id: Optional[int] = None,
    strict_location: bool = False,
    strict_budget: bool = False,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Intelligent alternative property matching engine.
    Only queries AVAILABLE properties belonging to the same company.
    Provides transparent match score and explainable advantages/compromises.
    Supports strict location and strict budget enforcement.
    """
    query = db.query(Property).filter(
        Property.company_id == company_id,
        Property.availability_status == PropertyStatus.AVAILABLE
    )

    if exclude_property_id:
        query = query.filter(Property.id != exclude_property_id)

    available_units = query.all()
    results = []

    for prop in available_units:
        score = 50  # Base score
        reasons = []
        compromises = []

        # Price check
        if max_price and max_price > 0:
            if prop.total_price <= max_price:
                diff = max_price - prop.total_price
                score += 25
                reasons.append(f"ضمن الميزانية (توفير {diff:,.0f} {prop.currency})")
            elif prop.total_price <= max_price * 1.1:
                if strict_budget:
                    continue
                score += 5
                compromises.append(f"أعلى من الميزانية قليلاً بـ {prop.total_price - max_price:,.0f} {prop.currency}")
            else:
                if strict_budget:
                    continue
                score -= 30
                compromises.append(f"أعلى بكثير من الميزانية (+{prop.total_price - max_price:,.0f} {prop.currency})")

        # Location check
        if preferred_location and preferred_location.strip():
            pref_loc = preferred_location.lower().strip()
            loc_matched = False
            prop_locs = [prop.location.lower(), prop.city.lower()]
            if prop.district:
                prop_locs.extend([prop.district.name_ar.lower(), prop.district.name_en.lower()])
            if prop.city_rel:
                prop_locs.extend([prop.city_rel.name_ar.lower(), prop.city_rel.name_en.lower()])
            if prop.governorate:
                prop_locs.extend([prop.governorate.name_ar.lower(), prop.governorate.name_en.lower()])

            for candidate in prop_locs:
                if pref_loc in candidate or candidate in pref_loc:
                    loc_matched = True
                    break

            if loc_matched:
                score += 25
                reasons.append(f"تطابق في الموقع: {prop.location}")
            else:
                if strict_location:
                    continue
                score -= 20
                compromises.append(f"موقع بديل: {prop.location}")

        # Bedrooms check
        if bedrooms and bedrooms > 0:
            if prop.bedrooms == bedrooms:
                score += 10
                reasons.append(f"{prop.bedrooms} Bedrooms as requested")
            elif prop.bedrooms > bedrooms:
                score += 5
                reasons.append(f"Extra space: {prop.bedrooms} Bedrooms")
            else:
                score -= 10
                compromises.append(f"Smaller unit: {prop.bedrooms} Bedrooms")

        # Down payment check
        if max_down_payment and max_down_payment > 0:
            if prop.down_payment <= max_down_payment:
                score += 10
                reasons.append(f"Affordable down payment ({prop.down_payment:,.0f} {prop.currency})")
            else:
                score -= 10
                compromises.append(f"Higher down payment ({prop.down_payment:,.0f} {prop.currency})")

        # Cap score between 10 and 99
        final_score = max(10, min(99, score))

        results.append({
            "property_id": prop.id,
            "unit_number": prop.unit_number,
            "project_name": prop.project.name if prop.project else "Independent",
            "property_type": prop.property_type,
            "location": prop.location,
            "city": prop.city,
            "area": prop.area,
            "bedrooms": prop.bedrooms,
            "bathrooms": prop.bathrooms,
            "total_price": prop.total_price,
            "currency": prop.currency,
            "down_payment": prop.down_payment,
            "installment_plan": prop.installment_plan,
            "match_score": final_score,
            "reasons": reasons,
            "compromises": compromises,
        })

    # Sort by highest match score
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:limit]
