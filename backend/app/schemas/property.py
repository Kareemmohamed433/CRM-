from typing import Optional, List
from pydantic import BaseModel, field_validator
from backend.app.models.models import PropertyStatus


class ProjectCreate(BaseModel):
    name: str
    developer: str
    location: str
    description: Optional[str] = ""
    project_type: str = "Residential"
    status: str = "Under Construction"


class ProjectOut(BaseModel):
    id: int
    company_id: int
    name: str
    developer: str
    location: str
    description: Optional[str]
    project_type: str
    status: str
    is_archived: bool = False
    available_units: int = 0

    class Config:
        from_attributes = True


class PropertyCreate(BaseModel):
    project_id: Optional[int] = None
    title: Optional[str] = None
    unit_number: str
    property_type: str = "Apartment"
    city: str = "Cairo"
    location: str = "New Cairo"
    governorate_id: Optional[int] = None
    city_id: Optional[int] = None
    district_id: Optional[int] = None
    area: float
    bedrooms: int = 2
    bathrooms: int = 2
    floor: int = 1
    view: str = "Landscape"
    finishing_status: str = "Semi-Finished"
    delivery_date: str = "2026-12-31"
    total_price: float
    currency: str = "EGP"
    down_payment: float = 0.0
    installment_plan: str = "8 Years Equal"
    installment_frequency: str = "Quarterly"
    remaining_balance: float = 0.0
    availability_status: PropertyStatus = PropertyStatus.AVAILABLE
    description: Optional[str] = ""

    @field_validator('total_price')
    @classmethod
    def validate_total_price(cls, v: float) -> float:
        if v is None or v <= 0:
            raise ValueError("يجب أن يكون السعر الإجمالي أكبر من صفر")
        return v

    @field_validator('area')
    @classmethod
    def validate_area(cls, v: float) -> float:
        if v is None or v <= 0:
            raise ValueError("يجب أن تكون المساحة أكبر من صفر")
        return v


class PropertyUpdate(BaseModel):
    project_id: Optional[int] = None
    title: Optional[str] = None
    unit_number: Optional[str] = None
    property_type: Optional[str] = None
    city: Optional[str] = None
    location: Optional[str] = None
    governorate_id: Optional[int] = None
    city_id: Optional[int] = None
    district_id: Optional[int] = None
    area: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    floor: Optional[int] = None
    view: Optional[str] = None
    finishing_status: Optional[str] = None
    delivery_date: Optional[str] = None
    total_price: Optional[float] = None
    down_payment: Optional[float] = None
    installment_plan: Optional[str] = None
    availability_status: Optional[PropertyStatus] = None
    is_archived: Optional[bool] = None
    description: Optional[str] = None


class PropertyVideoOut(BaseModel):
    id: int
    property_id: int
    company_id: int
    video_url: str
    video_type: str = "EXTERNAL"
    title: Optional[str] = None
    sort_order: int = 0

    class Config:
        from_attributes = True


class PropertyVideoCreate(BaseModel):
    video_url: str
    video_type: str = "EXTERNAL"
    title: Optional[str] = None
    sort_order: int = 0


class PropertyOut(BaseModel):
    id: int
    company_id: int
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    title: Optional[str] = None
    unit_number: str
    property_type: str
    city: str
    location: str
    governorate_id: Optional[int] = None
    city_id: Optional[int] = None
    district_id: Optional[int] = None
    area: float
    bedrooms: int
    bathrooms: int
    floor: int
    view: str
    finishing_status: str
    delivery_date: str
    total_price: float
    currency: str
    down_payment: float
    installment_plan: str
    installment_frequency: str
    remaining_balance: float
    availability_status: PropertyStatus
    is_archived: bool = False
    description: Optional[str] = ""
    images: List['PropertyImageOut'] = []
    videos: List[PropertyVideoOut] = []
    primary_image_url: Optional[str] = None

    class Config:
        from_attributes = True


class PropertyImageOut(BaseModel):
    id: int
    property_id: int
    company_id: int
    image_url: str
    caption: Optional[str] = None
    is_primary: bool = False
    sort_order: int = 0

    class Config:
        from_attributes = True


class PropertyFeatureOut(BaseModel):
    id: int
    property_id: int
    name: str
    value: str

    class Config:
        from_attributes = True


class AlternativePropertySearch(BaseModel):
    lead_id: Optional[int] = None
    max_price: Optional[float] = None
    preferred_location: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    max_down_payment: Optional[float] = None
