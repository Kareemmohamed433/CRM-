from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.core.permissions import get_current_user, require_roles
from backend.app.models.models import (
    Property, Project, User, UserRole, PropertyStatus, PropertyImage, PropertyVideo, PropertyFeature
)
from backend.app.schemas.property import (
    PropertyCreate, PropertyUpdate, PropertyOut, ProjectCreate, ProjectOut, AlternativePropertySearch,
    PropertyImageOut, PropertyVideoCreate, PropertyVideoOut, PropertyFeatureOut
)
from backend.app.services.matching_service import find_alternative_properties
from backend.app.services.audit_service import log_audit_event
from backend.app.services.storage_service import storage_service

router = APIRouter(tags=["Properties & Inventory"])


def _serialize_property(p: Property) -> PropertyOut:
    primary_img = None
    imgs = []
    if p.images:
        for img in p.images:
            imgs.append(PropertyImageOut(
                id=img.id,
                property_id=img.property_id,
                company_id=img.company_id,
                image_url=img.image_url,
                caption=img.caption,
                is_primary=img.is_primary,
                sort_order=img.sort_order
            ))
            if img.is_primary and not primary_img:
                primary_img = img.image_url
        if not primary_img and imgs:
            primary_img = imgs[0].image_url

    vids = []
    if p.videos:
        for vid in p.videos:
            vids.append(PropertyVideoOut(
                id=vid.id,
                property_id=vid.property_id,
                company_id=vid.company_id,
                video_url=vid.video_url,
                video_type=vid.video_type,
                title=vid.title,
                sort_order=vid.sort_order
            ))

    proj_name = p.project.name if p.project else "عقار مستقل"

    return PropertyOut(
        id=p.id,
        company_id=p.company_id,
        project_id=p.project_id,
        project_name=proj_name,
        title=p.title or f"{p.property_type} - {p.unit_number}",
        unit_number=p.unit_number,
        property_type=p.property_type,
        city=p.city or "",
        location=p.location or "",
        governorate_id=p.governorate_id,
        city_id=p.city_id,
        district_id=p.district_id,
        area=p.area,
        bedrooms=p.bedrooms,
        bathrooms=p.bathrooms,
        floor=p.floor,
        view=p.view or "",
        finishing_status=p.finishing_status or "",
        delivery_date=p.delivery_date or "",
        total_price=p.total_price,
        currency=p.currency or "EGP",
        down_payment=p.down_payment or 0.0,
        installment_plan=p.installment_plan or "",
        installment_frequency=p.installment_frequency or "",
        remaining_balance=p.remaining_balance or 0.0,
        availability_status=p.availability_status,
        is_archived=bool(p.is_archived),
        description=p.description or "",
        images=imgs,
        videos=vids,
        primary_image_url=primary_img
    )


# -------------------------------------------------------------------------
# Projects
# -------------------------------------------------------------------------

@router.get("/projects", response_model=List[ProjectOut])
def list_projects(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Project).filter(Project.company_id == current_user.company_id)
    if not include_archived:
        query = query.filter(Project.is_archived == False)
    projects = query.all()
    results = []
    for p in projects:
        avail_count = db.query(func.count(Property.id)).filter(
            Property.project_id == p.id,
            Property.availability_status == PropertyStatus.AVAILABLE,
            Property.is_archived == False
        ).scalar() or 0
        results.append(
            ProjectOut(
                id=p.id,
                company_id=p.company_id,
                name=p.name,
                developer=p.developer,
                location=p.location,
                description=p.description,
                project_type=p.project_type,
                status=p.status,
                is_archived=bool(p.is_archived),
                available_units=avail_count
            )
        )
    return results


@router.post("/projects", response_model=ProjectOut)
def create_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    proj = Project(
        company_id=current_user.company_id,
        name=project_in.name,
        developer=project_in.developer,
        location=project_in.location,
        description=project_in.description,
        project_type=project_in.project_type,
        status=project_in.status,
        is_archived=False
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return ProjectOut(
        id=proj.id,
        company_id=proj.company_id,
        name=proj.name,
        developer=proj.developer,
        location=proj.location,
        description=proj.description,
        project_type=proj.project_type,
        status=proj.status,
        is_archived=False,
        available_units=0
    )


@router.post("/projects/{project_id}/archive", response_model=ProjectOut)
def archive_project(
    project_id: int,
    archive: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    proj = db.query(Project).filter(
        Project.id == project_id,
        Project.company_id == current_user.company_id
    ).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    proj.is_archived = archive
    db.commit()
    db.refresh(proj)
    avail_count = db.query(func.count(Property.id)).filter(
        Property.project_id == proj.id,
        Property.availability_status == PropertyStatus.AVAILABLE,
        Property.is_archived == False
    ).scalar() or 0
    return ProjectOut(
        id=proj.id,
        company_id=proj.company_id,
        name=proj.name,
        developer=proj.developer,
        location=proj.location,
        description=proj.description,
        project_type=proj.project_type,
        status=proj.status,
        is_archived=bool(proj.is_archived),
        available_units=avail_count
    )


# -------------------------------------------------------------------------
# Properties
# -------------------------------------------------------------------------

@router.get("/properties", response_model=List[PropertyOut])
def list_properties(
    project_id: Optional[int] = None,
    governorate_id: Optional[int] = None,
    city_id: Optional[int] = None,
    district_id: Optional[int] = None,
    status: Optional[PropertyStatus] = None,
    property_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
    search: Optional[str] = None,
    include_archived: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Property).filter(Property.company_id == current_user.company_id)

    if not include_archived:
        query = query.filter(
            Property.is_archived == False,
            Property.availability_status != PropertyStatus.ARCHIVED
        )

    if project_id is not None:
        query = query.filter(Property.project_id == project_id)
    if governorate_id is not None:
        query = query.filter(Property.governorate_id == governorate_id)
    if city_id is not None:
        query = query.filter(Property.city_id == city_id)
    if district_id is not None:
        query = query.filter(Property.district_id == district_id)
    if status is not None:
        query = query.filter(Property.availability_status == status)
    if property_type:
        query = query.filter(Property.property_type.ilike(f"%{property_type}%"))
    if min_price is not None:
        query = query.filter(Property.total_price >= min_price)
    if max_price is not None:
        query = query.filter(Property.total_price <= max_price)
    if bedrooms is not None:
        query = query.filter(Property.bedrooms == bedrooms)
    if bathrooms is not None:
        query = query.filter(Property.bathrooms == bathrooms)
    if search:
        s = f"%{search}%"
        query = query.filter(
            (Property.unit_number.ilike(s)) |
            (Property.title.ilike(s)) |
            (Property.location.ilike(s)) |
            (Property.city.ilike(s))
        )

    properties = query.order_by(Property.total_price.asc()).offset(skip).limit(limit).all()
    return [_serialize_property(p) for p in properties]


@router.post("/properties", response_model=PropertyOut)
def create_property(
    prop_in: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    proj = None
    if prop_in.project_id:
        proj = db.query(Project).filter(
            Project.id == prop_in.project_id,
            Project.company_id == current_user.company_id
        ).first()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found in this company")

    if prop_in.total_price <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="يجب أن يكون السعر الإجمالي أكبر من صفر.")
    if prop_in.area <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="يجب أن تكون المساحة أكبر من صفر.")

    # Duplicate unit check within company & project (or independent)
    dup_query = db.query(Property).filter(
        Property.company_id == current_user.company_id,
        Property.unit_number == prop_in.unit_number.strip()
    )
    if prop_in.project_id:
        dup_query = dup_query.filter(Property.project_id == prop_in.project_id)
    else:
        dup_query = dup_query.filter(Property.project_id.is_(None))

    if dup_query.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"الوحدة رقم '{prop_in.unit_number}' مسجلة بالفعل."
        )

    title_val = prop_in.title or f"{prop_in.property_type} - {prop_in.unit_number}"

    new_prop = Property(
        company_id=current_user.company_id,
        project_id=prop_in.project_id,
        title=title_val,
        unit_number=prop_in.unit_number.strip(),
        property_type=prop_in.property_type,
        city=prop_in.city,
        location=prop_in.location,
        governorate_id=prop_in.governorate_id,
        city_id=prop_in.city_id,
        district_id=prop_in.district_id,
        area=prop_in.area,
        bedrooms=prop_in.bedrooms,
        bathrooms=prop_in.bathrooms,
        floor=prop_in.floor,
        view=prop_in.view,
        finishing_status=prop_in.finishing_status,
        delivery_date=prop_in.delivery_date,
        total_price=prop_in.total_price,
        currency=prop_in.currency,
        down_payment=prop_in.down_payment,
        installment_plan=prop_in.installment_plan,
        installment_frequency=prop_in.installment_frequency,
        remaining_balance=prop_in.remaining_balance,
        availability_status=prop_in.availability_status,
        is_archived=False,
        description=prop_in.description
    )
    db.add(new_prop)
    db.commit()
    db.refresh(new_prop)

    log_audit_event(
        db=db,
        company_id=current_user.company_id,
        action="CREATE_PROPERTY",
        entity_type="Property",
        entity_id=new_prop.id,
        actor_id=current_user.id,
        after_state={"unit_number": new_prop.unit_number, "price": new_prop.total_price}
    )

    return _serialize_property(new_prop)


@router.patch("/properties/{property_id}", response_model=PropertyOut)
def update_property(
    property_id: int,
    prop_in: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    before_state = {"status": prop.availability_status.value if prop.availability_status else None, "price": prop.total_price}

    update_data = prop_in.model_dump(exclude_unset=True)
    if "project_id" in update_data and update_data["project_id"] is not None:
        proj = db.query(Project).filter(
            Project.id == update_data["project_id"],
            Project.company_id == current_user.company_id
        ).first()
        if not proj:
            raise HTTPException(status_code=404, detail="Project not found in this company")

    for field, val in update_data.items():
        setattr(prop, field, val)

    if prop_in.is_archived is True and prop_in.availability_status is None:
        prop.availability_status = PropertyStatus.ARCHIVED
    elif prop_in.is_archived is False and prop.availability_status == PropertyStatus.ARCHIVED:
        prop.availability_status = PropertyStatus.AVAILABLE

    db.commit()
    db.refresh(prop)

    log_audit_event(
        db=db,
        company_id=current_user.company_id,
        action="UPDATE_PROPERTY",
        entity_type="Property",
        entity_id=prop.id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={"status": prop.availability_status.value if prop.availability_status else None, "price": prop.total_price}
    )

    return _serialize_property(prop)


@router.post("/properties/{property_id}/archive", response_model=PropertyOut)
def archive_property(
    property_id: int,
    archive: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    prop.is_archived = archive
    if archive:
        prop.availability_status = PropertyStatus.ARCHIVED
    else:
        if prop.availability_status == PropertyStatus.ARCHIVED:
            prop.availability_status = PropertyStatus.AVAILABLE
    db.commit()
    db.refresh(prop)
    return _serialize_property(prop)


@router.post("/properties/alternatives")
def get_alternative_properties(
    params: AlternativePropertySearch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alternatives = find_alternative_properties(
        db=db,
        company_id=current_user.company_id,
        max_price=params.max_price,
        preferred_location=params.preferred_location,
        property_type=params.property_type,
        bedrooms=params.bedrooms,
        max_down_payment=params.max_down_payment,
        limit=5
    )
    return alternatives


# -------------------------------------------------------------------------
# Property Details, Images & Videos
# -------------------------------------------------------------------------

@router.get("/properties/{property_id}", response_model=PropertyOut)
def get_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    return _serialize_property(prop)


@router.post("/properties/{property_id}/images", response_model=PropertyImageOut)
async def upload_property_image(
    property_id: int,
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    is_primary: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    content = await file.read()
    try:
        url = storage_service.save_property_image(content, file.filename or "image.jpg", file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # If first image or marked as primary, reset previous primaries
    existing_images = db.query(PropertyImage).filter(PropertyImage.property_id == property_id).all()
    if is_primary or len(existing_images) == 0:
        for img in existing_images:
            img.is_primary = False
        is_primary = True

    sort_order = len(existing_images) + 1
    new_image = PropertyImage(
        company_id=current_user.company_id,
        property_id=prop.id,
        image_url=url,
        caption=caption,
        is_primary=is_primary,
        sort_order=sort_order
    )
    db.add(new_image)
    db.commit()
    db.refresh(new_image)

    return PropertyImageOut(
        id=new_image.id,
        property_id=new_image.property_id,
        company_id=new_image.company_id,
        image_url=new_image.image_url,
        caption=new_image.caption,
        is_primary=new_image.is_primary,
        sort_order=new_image.sort_order
    )


@router.get("/properties/{property_id}/images", response_model=List[PropertyImageOut])
def list_property_images(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    images = db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id,
        PropertyImage.company_id == current_user.company_id
    ).order_by(PropertyImage.sort_order.asc()).all()

    return [
        PropertyImageOut(
            id=img.id,
            property_id=img.property_id,
            company_id=img.company_id,
            image_url=img.image_url,
            caption=img.caption,
            is_primary=img.is_primary,
            sort_order=img.sort_order
        )
        for img in images
    ]


@router.delete("/properties/{property_id}/images/{image_id}")
def delete_property_image(
    property_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    img = db.query(PropertyImage).filter(
        PropertyImage.id == image_id,
        PropertyImage.property_id == property_id,
        PropertyImage.company_id == current_user.company_id
    ).first()
    if not img:
        raise HTTPException(status_code=404, detail="Property image not found")

    # Delete physical file
    storage_service.delete_property_image(img.image_url)

    db.delete(img)
    db.commit()
    return {"status": "success", "message": "Image deleted successfully"}


@router.put("/properties/{property_id}/images/{image_id}/primary")
def set_primary_property_image(
    property_id: int,
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    images = db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id,
        PropertyImage.company_id == current_user.company_id
    ).all()

    target = None
    for img in images:
        if img.id == image_id:
            target = img
            img.is_primary = True
        else:
            img.is_primary = False

    if not target:
        raise HTTPException(status_code=404, detail="Property image not found")

    db.commit()
    return {"status": "success", "message": "Primary image set successfully"}


# -------------------------------------------------------------------------
# Property Videos (Upload & External links)
# -------------------------------------------------------------------------

@router.post("/properties/{property_id}/videos", response_model=PropertyVideoOut)
def add_property_external_video(
    property_id: int,
    video_in: PropertyVideoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    existing_vids = db.query(PropertyVideo).filter(PropertyVideo.property_id == property_id).all()
    sort_order = len(existing_vids) + 1

    vid = PropertyVideo(
        company_id=current_user.company_id,
        property_id=property_id,
        video_url=video_in.video_url,
        video_type=video_in.video_type or "EXTERNAL",
        title=video_in.title or "Property Video",
        sort_order=video_in.sort_order if video_in.sort_order > 0 else sort_order
    )
    db.add(vid)
    db.commit()
    db.refresh(vid)
    return vid


@router.post("/properties/{property_id}/videos/upload", response_model=PropertyVideoOut)
async def upload_property_video_file(
    property_id: int,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    content = await file.read()
    try:
        url = storage_service.save_property_video(content, file.filename or "video.mp4", file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing_vids = db.query(PropertyVideo).filter(PropertyVideo.property_id == property_id).all()
    sort_order = len(existing_vids) + 1

    vid = PropertyVideo(
        company_id=current_user.company_id,
        property_id=property_id,
        video_url=url,
        video_type="UPLOAD",
        title=title or file.filename or "Uploaded Video",
        sort_order=sort_order
    )
    db.add(vid)
    db.commit()
    db.refresh(vid)
    return vid


@router.get("/properties/{property_id}/videos", response_model=List[PropertyVideoOut])
def list_property_videos(
    property_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    prop = db.query(Property).filter(
        Property.id == property_id,
        Property.company_id == current_user.company_id
    ).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")

    videos = db.query(PropertyVideo).filter(
        PropertyVideo.property_id == property_id,
        PropertyVideo.company_id == current_user.company_id
    ).order_by(PropertyVideo.sort_order.asc()).all()
    return videos


@router.delete("/properties/{property_id}/videos/{video_id}")
def delete_property_video(
    property_id: int,
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.COMPANY_ADMIN, UserRole.SALES_MANAGER, UserRole.SUPER_ADMIN]))
):
    vid = db.query(PropertyVideo).filter(
        PropertyVideo.id == video_id,
        PropertyVideo.property_id == property_id,
        PropertyVideo.company_id == current_user.company_id
    ).first()
    if not vid:
        raise HTTPException(status_code=404, detail="Property video not found")

    if vid.video_type == "UPLOAD":
        storage_service.delete_property_video(vid.video_url)

    db.delete(vid)
    db.commit()
    return {"status": "success", "message": "Video deleted successfully"}


