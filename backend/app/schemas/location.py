from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DistrictBase(BaseModel):
    name_ar: str
    name_en: str
    city_id: int
    is_active: bool = True


class DistrictCreate(BaseModel):
    name_ar: str
    name_en: str
    city_id: int
    is_active: bool = True


class DistrictUpdate(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    is_active: Optional[bool] = None


class DistrictOut(DistrictBase):
    id: int
    created_at: datetime
    properties_count: Optional[int] = 0
    projects_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class CityBase(BaseModel):
    name_ar: str
    name_en: str
    governorate_id: int
    is_active: bool = True


class CityCreate(BaseModel):
    name_ar: str
    name_en: str
    governorate_id: int
    is_active: bool = True


class CityUpdate(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    is_active: Optional[bool] = None


class CityOut(CityBase):
    id: int
    created_at: datetime
    districts_count: Optional[int] = 0
    properties_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class GovernorateBase(BaseModel):
    name_ar: str
    name_en: str
    is_active: bool = True


class GovernorateCreate(BaseModel):
    name_ar: str
    name_en: str
    is_active: bool = True


class GovernorateUpdate(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    is_active: Optional[bool] = None


class GovernorateOut(GovernorateBase):
    id: int
    created_at: datetime
    cities_count: Optional[int] = 0
    properties_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class HierarchyDistrict(BaseModel):
    id: int
    name_ar: str
    name_en: str
    is_active: bool
    projects_count: int = 0
    properties_count: int = 0


class HierarchyCity(BaseModel):
    id: int
    name_ar: str
    name_en: str
    is_active: bool
    districts: List[HierarchyDistrict] = []


class HierarchyGovernorate(BaseModel):
    id: int
    name_ar: str
    name_en: str
    is_active: bool
    cities: List[HierarchyCity] = []

