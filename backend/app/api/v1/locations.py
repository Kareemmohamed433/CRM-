from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user
from backend.app.models.models import (
    User, UserRole, Governorate, City, District, Project, Property
)
from backend.app.schemas.location import (
    GovernorateCreate, GovernorateUpdate, GovernorateOut,
    CityCreate, CityUpdate, CityOut,
    DistrictCreate, DistrictUpdate, DistrictOut,
    HierarchyGovernorate, HierarchyCity, HierarchyDistrict
)

router = APIRouter(prefix="/locations", tags=["Locations"])


def check_location_admin(current_user: User):
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ليس لديك صلاحية إدارة المواقع والمناطق"
        )


# -------------------------------------------------------------------------
# Hierarchy
# -------------------------------------------------------------------------

@router.get("/hierarchy", response_model=List[HierarchyGovernorate])
def get_location_hierarchy(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns complete nested location hierarchy: Governorate -> City -> District."""
    govs = db.query(Governorate).filter(Governorate.is_active == True).all()  # noqa: E712
    result = []

    for gov in govs:
        cities = db.query(City).filter(
            City.governorate_id == gov.id,
            City.is_active == True  # noqa: E712
        ).all()

        h_cities = []
        for city in cities:
            districts = db.query(District).filter(
                District.city_id == city.id,
                District.is_active == True  # noqa: E712
            ).all()

            h_districts = []
            for d in districts:
                props_count = db.query(func.count(Property.id)).filter(Property.district_id == d.id).scalar() or 0
                projs_count = db.query(func.count(Project.id)).filter(Project.district_id == d.id).scalar() or 0
                h_districts.append(HierarchyDistrict(
                    id=d.id,
                    name_ar=d.name_ar,
                    name_en=d.name_en,
                    is_active=d.is_active,
                    projects_count=projs_count,
                    properties_count=props_count
                ))

            h_cities.append(HierarchyCity(
                id=city.id,
                name_ar=city.name_ar,
                name_en=city.name_en,
                is_active=city.is_active,
                districts=h_districts
            ))

        result.append(HierarchyGovernorate(
            id=gov.id,
            name_ar=gov.name_ar,
            name_en=gov.name_en,
            is_active=gov.is_active,
            cities=h_cities
        ))

    return result


# -------------------------------------------------------------------------
# Governorates CRUD
# -------------------------------------------------------------------------

@router.get("/governorates", response_model=List[GovernorateOut])
def list_governorates(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Governorate)
    if is_active is not None:
        query = query.filter(Governorate.is_active == is_active)
    govs = query.order_by(Governorate.name_ar.asc()).all()

    out = []
    for g in govs:
        c_count = db.query(func.count(City.id)).filter(City.governorate_id == g.id).scalar() or 0
        p_count = db.query(func.count(Property.id)).filter(Property.governorate_id == g.id).scalar() or 0
        g_dict = {
            "id": g.id,
            "name_ar": g.name_ar,
            "name_en": g.name_en,
            "is_active": g.is_active,
            "created_at": g.created_at,
            "cities_count": c_count,
            "properties_count": p_count,
        }
        out.append(GovernorateOut(**g_dict))
    return out


@router.post("/governorates", response_model=GovernorateOut, status_code=status.HTTP_201_CREATED)
def create_governorate(
    data: GovernorateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_location_admin(current_user)
    existing = db.query(Governorate).filter(
        (Governorate.name_ar == data.name_ar) | (Governorate.name_en == data.name_en)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="المحافظة مسجلة بالفعل بهذا الاسم")

    gov = Governorate(
        company_id=current_user.company_id,
        name_ar=data.name_ar.strip(),
        name_en=data.name_en.strip(),
        is_active=data.is_active
    )
    db.add(gov)
    db.commit()
    db.refresh(gov)
    return GovernorateOut(
        id=gov.id,
        name_ar=gov.name_ar,
        name_en=gov.name_en,
        is_active=gov.is_active,
        created_at=gov.created_at,
        cities_count=0,
        properties_count=0
    )


@router.put("/governorates/{gov_id}", response_model=GovernorateOut)
def update_governorate(
    gov_id: int,
    data: GovernorateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_location_admin(current_user)
    gov = db.query(Governorate).filter(Governorate.id == gov_id).first()
    if not gov:
        raise HTTPException(status_code=404, detail="المحافظة غير موجودة")

    if data.name_ar is not None:
        gov.name_ar = data.name_ar.strip()
    if data.name_en is not None:
        gov.name_en = data.name_en.strip()
    if data.is_active is not None:
        gov.is_active = data.is_active

    db.commit()
    db.refresh(gov)
    c_count = db.query(func.count(City.id)).filter(City.governorate_id == gov.id).scalar() or 0
    p_count = db.query(func.count(Property.id)).filter(Property.governorate_id == gov.id).scalar() or 0
    return GovernorateOut(
        id=gov.id,
        name_ar=gov.name_ar,
        name_en=gov.name_en,
        is_active=gov.is_active,
        created_at=gov.created_at,
        cities_count=c_count,
        properties_count=p_count
    )


@router.delete("/governorates/{gov_id}")
def delete_governorate(
    gov_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_location_admin(current_user)
    gov = db.query(Governorate).filter(Governorate.id == gov_id).first()
    if not gov:
        raise HTTPException(status_code=404, detail="المحافظة غير موجودة")

    cities_count = db.query(func.count(City.id)).filter(City.governorate_id == gov_id).scalar() or 0
    if cities_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"لا يمكن حذف المحافظة لاحتوائها على {cities_count} مدينة مرتبطة. يمكنك تعطيلها بدلاً من الحذف."
        )

    props_count = db.query(func.count(Property.id)).filter(Property.governorate_id == gov_id).scalar() or 0
    if props_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"لا يمكن حذف المحافظة لاحتوائها على {props_count} عقار مرتبط بها."
        )

    db.delete(gov)
    db.commit()
    return {"message": "تم حذف المحافظة بنجاح"}


# -------------------------------------------------------------------------
# Cities CRUD
# -------------------------------------------------------------------------

@router.get("/cities", response_model=List[CityOut])
def list_cities(
    governorate_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(City)
    if governorate_id is not None:
        query = query.filter(City.governorate_id == governorate_id)
    if is_active is not None:
        query = query.filter(City.is_active == is_active)

    cities = query.order_by(City.name_ar.asc()).all()
    out = []
    for c in cities:
        d_count = db.query(func.count(District.id)).filter(District.city_id == c.id).scalar() or 0
        p_count = db.query(func.count(Property.id)).filter(Property.city_id == c.id).scalar() or 0
        out.append(CityOut(
            id=c.id,
            governorate_id=c.governorate_id,
            name_ar=c.name_ar,
            name_en=c.name_en,
            is_active=c.is_active,
            created_at=c.created_at,
            districts_count=d_count,
            properties_count=p_count
        ))
    return out


@router.post("/cities", response_model=CityOut, status_code=status.HTTP_201_CREATED)
def create_city(
    data: CityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_location_admin(current_user)
    gov = db.query(Governorate).filter(Governorate.id == data.governorate_id).first()
    if not gov:
        raise HTTPException(status_code=404, detail="المحافظة المحددة غير موجودة")

    city = City(
        governorate_id=data.governorate_id,
        company_id=current_user.company_id,
        name_ar=data.name_ar.strip(),
        name_en=data.name_en.strip(),
        is_active=data.is_active
    )
    db.add(city)
    db.commit()
    db.refresh(city)
    return CityOut(
        id=city.id,
        governorate_id=city.governorate_id,
        name_ar=city.name_ar,
        name_en=city.name_en,
        is_active=city.is_active,
        created_at=city.created_at,
        districts_count=0,
        properties_count=0
    )


@router.put("/cities/{city_id}", response_model=CityOut)
def update_city(
    city_id: int,
    data: CityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_location_admin(current_user)
    city = db.query(City).filter(City.id == city_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="المدينة غير موجودة")

    if data.name_ar is not None:
        city.name_ar = data.name_ar.strip()
    if data.name_en is not None:
        city.name_en = data.name_en.strip()
    if data.is_active is not None:
        city.is_active = data.is_active

    db.commit()
    db.refresh(city)
    d_count = db.query(func.count(District.id)).filter(District.city_id == city.id).scalar() or 0
    p_count = db.query(func.count(Property.id)).filter(Property.city_id == city.id).scalar() or 0
    return CityOut(
        id=city.id,
        governorate_id=city.governorate_id,
        name_ar=city.name_ar,
        name_en=city.name_en,
        is_active=city.is_active,
        created_at=city.created_at,
        districts_count=d_count,
        properties_count=p_count
    )


@router.delete("/cities/{city_id}")
def delete_city(
    city_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_location_admin(current_user)
    city = db.query(City).filter(City.id == city_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="المدينة غير موجودة")

    districts_count = db.query(func.count(District.id)).filter(District.city_id == city_id).scalar() or 0
    if districts_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"لا يمكن حذف المدينة لاحتوائها على {districts_count} منطقة/حي مرتبطة. يمكنك تعطيلها بدلاً من الحذف."
        )

    props_count = db.query(func.count(Property.id)).filter(Property.city_id == city_id).scalar() or 0
    if props_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"لا يمكن حذف المدينة لاحتوائها على {props_count} عقار مرتبط بها."
        )

    db.delete(city)
    db.commit()
    return {"message": "تم حذف المدينة بنجاح"}


# -------------------------------------------------------------------------
# Districts CRUD
# -------------------------------------------------------------------------

@router.get("/districts", response_model=List[DistrictOut])
def list_districts(
    city_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(District)
    if city_id is not None:
        query = query.filter(District.city_id == city_id)
    if is_active is not None:
        query = query.filter(District.is_active == is_active)

    districts = query.order_by(District.name_ar.asc()).all()
    out = []
    for d in districts:
        projs = db.query(func.count(Project.id)).filter(Project.district_id == d.id).scalar() or 0
        props = db.query(func.count(Property.id)).filter(Property.district_id == d.id).scalar() or 0
        out.append(DistrictOut(
            id=d.id,
            city_id=d.city_id,
            name_ar=d.name_ar,
            name_en=d.name_en,
            is_active=d.is_active,
            created_at=d.created_at,
            projects_count=projs,
            properties_count=props
        ))
    return out


@router.post("/districts", response_model=DistrictOut, status_code=status.HTTP_201_CREATED)
def create_district(
    data: DistrictCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_location_admin(current_user)
    city = db.query(City).filter(City.id == data.city_id).first()
    if not city:
        raise HTTPException(status_code=404, detail="المدينة المحددة غير موجودة")

    district = District(
        city_id=data.city_id,
        company_id=current_user.company_id,
        name_ar=data.name_ar.strip(),
        name_en=data.name_en.strip(),
        is_active=data.is_active
    )
    db.add(district)
    db.commit()
    db.refresh(district)
    return DistrictOut(
        id=district.id,
        city_id=district.city_id,
        name_ar=district.name_ar,
        name_en=district.name_en,
        is_active=district.is_active,
        created_at=district.created_at,
        projects_count=0,
        properties_count=0
    )


@router.put("/districts/{district_id}", response_model=DistrictOut)
def update_district(
    district_id: int,
    data: DistrictUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_location_admin(current_user)
    district = db.query(District).filter(District.id == district_id).first()
    if not district:
        raise HTTPException(status_code=404, detail="المنطقة/الحي غير موجود")

    if data.name_ar is not None:
        district.name_ar = data.name_ar.strip()
    if data.name_en is not None:
        district.name_en = data.name_en.strip()
    if data.is_active is not None:
        district.is_active = data.is_active

    db.commit()
    db.refresh(district)
    projs = db.query(func.count(Project.id)).filter(Project.district_id == district.id).scalar() or 0
    props = db.query(func.count(Property.id)).filter(Property.district_id == district.id).scalar() or 0
    return DistrictOut(
        id=district.id,
        city_id=district.city_id,
        name_ar=district.name_ar,
        name_en=district.name_en,
        is_active=district.is_active,
        created_at=district.created_at,
        projects_count=projs,
        properties_count=props
    )


@router.delete("/districts/{district_id}")
def delete_district(
    district_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    check_location_admin(current_user)
    district = db.query(District).filter(District.id == district_id).first()
    if not district:
        raise HTTPException(status_code=404, detail="المنطقة/الحي غير موجود")

    projs_count = db.query(func.count(Project.id)).filter(Project.district_id == district_id).scalar() or 0
    if projs_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"لا يمكن حذف المنطقة لاحتوائها على {projs_count} كمبوند/مشروع مرتبط بها."
        )

    props_count = db.query(func.count(Property.id)).filter(Property.district_id == district_id).scalar() or 0
    if props_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"لا يمكن حذف المنطقة لاحتوائها على {props_count} عقار مرتبط بها."
        )

    db.delete(district)
    db.commit()
    return {"message": "تم حذف المنطقة بنجاح"}
