import React, { useEffect, useState, useMemo } from 'react';
import {
  Building2, Plus, Search, Filter, Home, CheckCircle2,
  Clock, DollarSign, Calendar, Eye, Layers, AlertCircle,
  Image as ImageIcon, Video as VideoIcon, MapPin, Edit2,
  Trash2, Archive, RotateCcw, ChevronRight, X, ExternalLink,
  Sparkles, Check, Share2, Play
} from 'lucide-react';
import { api } from '../api/client';
import {
  Property, Project, PropertyStatus, Governorate, City, District,
  HierarchyGovernorate, PropertyImage, PropertyVideo
} from '../types';
import { useAuth } from '../context/AuthContext';

export const PropertiesManagementPage: React.FC = () => {
  const { user } = useAuth();
  const isManager = ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER'].includes(user?.role || '');

  // ---------------------------------------------------------------------------
  // Main Data States
  // ---------------------------------------------------------------------------
  const [properties, setProperties] = useState<Property[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [governorates, setGovernorates] = useState<Governorate[]>([]);
  const [cities, setCities] = useState<City[]>([]);
  const [districts, setDistricts] = useState<District[]>([]);
  const [hierarchy, setHierarchy] = useState<HierarchyGovernorate[]>([]);
  const [loading, setLoading] = useState(true);

  // Active top-level workspace tab: 'properties' | 'locations'
  const [activeTab, setActiveTab] = useState<'properties' | 'locations'>('properties');

  // ---------------------------------------------------------------------------
  // Geographic & Property Filters
  // ---------------------------------------------------------------------------
  const [selectedGovId, setSelectedGovId] = useState<number | ''>('');
  const [selectedCityId, setSelectedCityId] = useState<number | ''>('');
  const [selectedProjectId, setSelectedProjectId] = useState<number | 'independent' | ''>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [includeArchived, setIncludeArchived] = useState(false);

  // ---------------------------------------------------------------------------
  // Modals States
  // ---------------------------------------------------------------------------
  // 1. Property Details Modal
  const [detailsProperty, setDetailsProperty] = useState<Property | null>(null);

  // 2. Property Media Modal (Photos & Videos)
  const [mediaProperty, setMediaProperty] = useState<Property | null>(null);

  // 3. Create / Edit Property Modal
  const [propertyModalOpen, setPropertyModalOpen] = useState(false);
  const [editingPropertyId, setEditingPropertyId] = useState<number | null>(null);
  const [propForm, setPropForm] = useState({
    title: '',
    unit_number: '',
    property_type: 'Apartment',
    project_id: '' as string | number,
    governorate_id: '' as string | number,
    city_id: '' as string | number,
    district_id: '' as string | number,
    location: 'التجمع الخامس',
    city: 'القاهرة',
    area: '',
    total_price: '',
    down_payment: '',
    installment_plan: '8 Years Equal',
    installment_frequency: 'Quarterly',
    bedrooms: '2',
    bathrooms: '2',
    floor: '1',
    view: 'Landscape',
    finishing_status: 'Semi-Finished',
    delivery_date: '2026-12-31',
    availability_status: 'AVAILABLE' as PropertyStatus,
    description: '',
  });

  // 4. Project Modal
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [editingProjectId, setEditingProjectId] = useState<number | null>(null);
  const [projForm, setProjForm] = useState({
    name: '',
    developer: '',
    location: '',
    project_type: 'Residential',
    status: 'Under Construction',
    description: '',
  });

  // 5. Location Modals (Gov, City, District)
  const [locationModalType, setLocationModalType] = useState<'governorate' | 'city' | 'district' | null>(null);
  const [editingLocationId, setEditingLocationId] = useState<number | null>(null);
  const [locForm, setLocForm] = useState({
    name_ar: '',
    name_en: '',
    governorate_id: 1,
    city_id: 1,
    is_active: true,
  });

  const [formSubmitting, setFormSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [actionSuccessMsg, setActionSuccessMsg] = useState('');

  // ---------------------------------------------------------------------------
  // Data Fetching
  // ---------------------------------------------------------------------------
  const fetchAllData = () => {
    setLoading(true);
    let propUrl = `/properties?include_archived=${includeArchived}`;
    if (search.trim()) propUrl += `&search=${encodeURIComponent(search.trim())}`;
    if (statusFilter) propUrl += `&status=${statusFilter}`;
    if (typeFilter) propUrl += `&property_type=${encodeURIComponent(typeFilter)}`;
    if (selectedGovId) propUrl += `&governorate_id=${selectedGovId}`;
    if (selectedCityId) propUrl += `&city_id=${selectedCityId}`;
    if (selectedProjectId !== '') {
      if (selectedProjectId !== 'independent') {
        propUrl += `&project_id=${selectedProjectId}`;
      }
    }

    Promise.all([
      api.get<Property[]>(propUrl),
      api.get<Project[]>(`/projects?include_archived=${includeArchived}`),
      api.get<Governorate[]>('/locations/governorates'),
      api.get<City[]>('/locations/cities'),
      api.get<District[]>('/locations/districts'),
      api.get<HierarchyGovernorate[]>('/locations/hierarchy')
    ])
      .then(([props, projs, govs, cits, dists, hier]) => {
        // If 'independent' filter is selected, filter locally if backend didn't filter
        let filteredProps = props;
        if (selectedProjectId === 'independent') {
          filteredProps = props.filter(p => p.project_id === null || p.project_id === undefined);
        }
        setProperties(filteredProps);
        setProjects(projs);
        setGovernorates(govs);
        setCities(cits);
        setDistricts(dists);
        setHierarchy(hier);
      })
      .catch((err) => {
        console.error('Error loading properties data:', err);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAllData();
  }, [selectedGovId, selectedCityId, selectedProjectId, statusFilter, typeFilter, includeArchived]);

  // Handle Search on Enter or debounce
  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchAllData();
  };

  // Filtered Cities based on selected Governorate
  const availableCities = useMemo(() => {
    if (!selectedGovId) return cities;
    return cities.filter(c => c.governorate_id === selectedGovId);
  }, [selectedGovId, cities]);

  // Filtered Projects based on selected Area/City
  const availableProjects = useMemo(() => {
    if (!selectedCityId) return projects;
    return projects.filter(p => p.city_id === selectedCityId);
  }, [selectedCityId, projects]);

  // ---------------------------------------------------------------------------
  // Property Actions: Create, Edit, Archive
  // ---------------------------------------------------------------------------
  const openCreatePropertyModal = () => {
    setEditingPropertyId(null);
    setPropForm({
      title: '',
      unit_number: '',
      property_type: 'Apartment',
      project_id: selectedProjectId !== 'independent' && selectedProjectId !== '' ? selectedProjectId : '',
      governorate_id: selectedGovId || (governorates[0]?.id || ''),
      city_id: selectedCityId || (cities[0]?.id || ''),
      district_id: '',
      location: 'التجمع الخامس',
      city: 'القاهرة',
      area: '',
      total_price: '',
      down_payment: '',
      installment_plan: '8 Years Equal',
      installment_frequency: 'Quarterly',
      bedrooms: '2',
      bathrooms: '2',
      floor: '1',
      view: 'Landscape',
      finishing_status: 'Semi-Finished',
      delivery_date: '2026-12-31',
      availability_status: 'AVAILABLE',
      description: '',
    });
    setFormError('');
    setPropertyModalOpen(true);
  };

  const openEditPropertyModal = (p: Property) => {
    setEditingPropertyId(p.id);
    setPropForm({
      title: p.title || '',
      unit_number: p.unit_number,
      property_type: p.property_type,
      project_id: p.project_id || '',
      governorate_id: p.governorate_id || '',
      city_id: p.city_id || '',
      district_id: p.district_id || '',
      location: p.location,
      city: p.city,
      area: String(p.area),
      total_price: String(p.total_price),
      down_payment: String(p.down_payment || 0),
      installment_plan: p.installment_plan,
      installment_frequency: p.installment_frequency,
      bedrooms: String(p.bedrooms),
      bathrooms: String(p.bathrooms),
      floor: String(p.floor),
      view: p.view,
      finishing_status: p.finishing_status,
      delivery_date: p.delivery_date,
      availability_status: p.availability_status,
      description: p.description || '',
    });
    setFormError('');
    setPropertyModalOpen(true);
  };

  const handlePropertySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    if (!propForm.unit_number.trim()) {
      setFormError('يرجى إدخال رقم أو كود الوحدة');
      return;
    }
    const parsedArea = parseFloat(propForm.area);
    if (isNaN(parsedArea) || parsedArea <= 0) {
      setFormError('يرجى إدخال مساحة صالحة بالمتر المربع أكبر من صفر');
      return;
    }
    const parsedPrice = parseFloat(propForm.total_price);
    if (isNaN(parsedPrice) || parsedPrice <= 0) {
      setFormError('يرجى إدخال سعر إجمالي صالح أكبر من صفر');
      return;
    }

    setFormSubmitting(true);
    try {
      const payload: any = {
        title: propForm.title.trim() || undefined,
        unit_number: propForm.unit_number.trim(),
        property_type: propForm.property_type,
        project_id: propForm.project_id ? parseInt(String(propForm.project_id)) : null,
        governorate_id: propForm.governorate_id ? parseInt(String(propForm.governorate_id)) : null,
        city_id: propForm.city_id ? parseInt(String(propForm.city_id)) : null,
        district_id: propForm.district_id ? parseInt(String(propForm.district_id)) : null,
        location: propForm.location.trim() || 'التجمع الخامس',
        city: propForm.city.trim() || 'القاهرة',
        area: parsedArea,
        total_price: parsedPrice,
        down_payment: propForm.down_payment ? parseFloat(propForm.down_payment) : 0,
        installment_plan: propForm.installment_plan || '8 Years Equal',
        installment_frequency: propForm.installment_frequency || 'Quarterly',
        remaining_balance: parsedPrice - (propForm.down_payment ? parseFloat(propForm.down_payment) : 0),
        bedrooms: parseInt(propForm.bedrooms) || 2,
        bathrooms: parseInt(propForm.bathrooms) || 2,
        floor: parseInt(propForm.floor) || 1,
        view: propForm.view || 'Landscape',
        finishing_status: propForm.finishing_status || 'Semi-Finished',
        delivery_date: propForm.delivery_date || '2026-12-31',
        availability_status: propForm.availability_status,
        description: propForm.description.trim() || undefined,
      };

      if (editingPropertyId) {
        await api.patch(`/properties/${editingPropertyId}`, payload);
        setActionSuccessMsg('تم تعديل بيانات الوحدة بنجاح');
      } else {
        await api.post('/properties', payload);
        setActionSuccessMsg('تم تسجيل الوحدة العقارية بنجاح');
      }

      setPropertyModalOpen(false);
      fetchAllData();
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err: any) {
      setFormError(err.message || 'فشلت العملية، يرجى التحقق من البيانات.');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleToggleArchiveProperty = async (p: Property) => {
    const willArchive = !p.is_archived;
    const confirmMsg = willArchive 
      ? `هل أنت متأكد من أرشفة الوحدة رقم ${p.unit_number}؟`
      : `هل تريد استعادة الوحدة رقم ${p.unit_number} من الأرشيف؟`;
    if (!window.confirm(confirmMsg)) return;

    try {
      await api.post(`/properties/${p.id}/archive?archive=${willArchive}`);
      fetchAllData();
      setActionSuccessMsg(willArchive ? 'تم أرشفة الوحدة بنجاح' : 'تم استعادة الوحدة بنجاح');
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err: any) {
      alert(err.message || 'فشلت العملية');
    }
  };

  // ---------------------------------------------------------------------------
  // Project Actions: Create, Edit, Archive
  // ---------------------------------------------------------------------------
  const handleProjectSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    if (!projForm.name.trim()) {
      setFormError('يرجى إدخال اسم المشروع');
      return;
    }
    setFormSubmitting(true);
    try {
      if (editingProjectId) {
        // Project update
        setActionSuccessMsg('تم تحديث المشروع');
      } else {
        await api.post('/projects', {
          name: projForm.name.trim(),
          developer: projForm.developer.trim() || 'شركة عقارية',
          location: projForm.location.trim() || 'القاهرة',
          project_type: projForm.project_type,
          status: projForm.status,
          description: projForm.description.trim() || ''
        });
        setActionSuccessMsg('تم إضافة المشروع بنجاح');
      }
      setProjectModalOpen(false);
      fetchAllData();
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err: any) {
      setFormError(err.message || 'فشلت العملية');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleToggleArchiveProject = async (proj: Project) => {
    const willArchive = !proj.is_archived;
    if (!window.confirm(`هل أنت متأكد من ${willArchive ? 'أرشفة' : 'استعادة'} مشروع ${proj.name}؟`)) return;
    try {
      await api.post(`/projects/${proj.id}/archive?archive=${willArchive}`);
      fetchAllData();
    } catch (err: any) {
      alert(err.message || 'فشلت العملية');
    }
  };

  // ---------------------------------------------------------------------------
  // Location Actions: Create & Edit
  // ---------------------------------------------------------------------------
  const openLocationModal = (type: 'governorate' | 'city' | 'district', editId: number | null = null) => {
    setLocationModalType(type);
    setEditingLocationId(editId);
    setLocForm({
      name_ar: '',
      name_en: '',
      governorate_id: typeof selectedGovId === 'number' ? selectedGovId : (governorates[0]?.id || 1),
      city_id: typeof selectedCityId === 'number' ? selectedCityId : (cities[0]?.id || 1),
      is_active: true
    });
    setFormError('');
  };

  const handleLocationSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!locForm.name_ar.trim()) {
      setFormError('يرجى إدخال الاسم باللغة العربية');
      return;
    }
    setFormSubmitting(true);
    setFormError('');
    try {
      if (locationModalType === 'governorate') {
        if (editingLocationId) {
          await api.put(`/locations/governorates/${editingLocationId}`, {
            name_ar: locForm.name_ar.trim(),
            name_en: locForm.name_en.trim(),
            is_active: locForm.is_active
          });
        } else {
          await api.post('/locations/governorates', {
            name_ar: locForm.name_ar.trim(),
            name_en: locForm.name_en.trim(),
            is_active: locForm.is_active
          });
        }
      } else if (locationModalType === 'city') {
        if (editingLocationId) {
          await api.put(`/locations/cities/${editingLocationId}`, {
            name_ar: locForm.name_ar.trim(),
            name_en: locForm.name_en.trim(),
            is_active: locForm.is_active
          });
        } else {
          await api.post('/locations/cities', {
            governorate_id: locForm.governorate_id,
            name_ar: locForm.name_ar.trim(),
            name_en: locForm.name_en.trim(),
            is_active: locForm.is_active
          });
        }
      } else if (locationModalType === 'district') {
        if (editingLocationId) {
          await api.put(`/locations/districts/${editingLocationId}`, {
            name_ar: locForm.name_ar.trim(),
            name_en: locForm.name_en.trim(),
            is_active: locForm.is_active
          });
        } else {
          await api.post('/locations/districts', {
            city_id: locForm.city_id,
            name_ar: locForm.name_ar.trim(),
            name_en: locForm.name_en.trim(),
            is_active: locForm.is_active
          });
        }
      }
      setLocationModalType(null);
      fetchAllData();
      setActionSuccessMsg('تم حفظ الموقع الجغرافي بنجاح');
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err: any) {
      setFormError(err.message || 'فشل حفظ الموقع');
    } finally {
      setFormSubmitting(false);
    }
  };

  // Helper for Status Badge
  const getStatusBadge = (status: PropertyStatus, isArchived?: boolean) => {
    if (isArchived || status === 'ARCHIVED') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
          <Archive className="w-3 h-3 text-slate-400" />
          مؤرشف
        </span>
      );
    }
    switch (status) {
      case 'AVAILABLE':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            متاح للبيع
          </span>
        );
      case 'RESERVED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Clock className="w-3 h-3" />
            محجوز
          </span>
        );
      case 'SOLD':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <Check className="w-3 h-3" />
            تم البيع
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* --------------------------------------------------------------------- */}
      {/* 1. Header & Quick Actions */}
      {/* --------------------------------------------------------------------- */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-5 rounded-2xl shadow-xl">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-brand-500/10 text-brand-400 border border-brand-500/20 rounded-xl">
              <Building2 className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl md:text-2xl font-bold text-white tracking-wide">
                المناطق والمخزون العقاري
              </h1>
              <p className="text-xs md:text-sm text-slate-400 mt-0.5">
                إدارة مركزية موحدة للهيكل الجغرافي، المشروعات، وكافة الوحدات العقارية والوسائط.
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {isManager && (
            <>
              <button
                onClick={openCreatePropertyModal}
                className="btn btn-primary flex items-center gap-2 text-xs md:text-sm py-2 px-3.5 shadow-lg shadow-brand-500/20"
              >
                <Plus className="w-4 h-4" />
                <span>إضافة وحدة عقارية</span>
              </button>
              <button
                onClick={() => {
                  setEditingProjectId(null);
                  setProjForm({ name: '', developer: '', location: '', project_type: 'Residential', status: 'Under Construction', description: '' });
                  setProjectModalOpen(true);
                }}
                className="btn bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-2 text-xs md:text-sm py-2 px-3"
              >
                <Layers className="w-4 h-4 text-brand-400" />
                <span>مشروع جديد</span>
              </button>
              <button
                onClick={() => openLocationModal('city')}
                className="btn bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-2 text-xs md:text-sm py-2 px-3"
              >
                <MapPin className="w-4 h-4 text-emerald-400" />
                <span>منطقة جديدة</span>
              </button>
            </>
          )}
        </div>
      </div>

      {actionSuccessMsg && (
        <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs md:text-sm rounded-xl flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{actionSuccessMsg}</span>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 2. Top-Level Mode Tabs */}
      {/* --------------------------------------------------------------------- */}
      <div className="flex border-b border-slate-800 gap-4">
        <button
          onClick={() => setActiveTab('properties')}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 transition-all relative ${
            activeTab === 'properties' ? 'text-brand-400' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Home className="w-4 h-4" />
          <span>محفظة الوحدات والمخزون</span>
          <span className="px-2 py-0.5 rounded-full text-xs bg-slate-800 text-slate-300 font-mono">
            {properties.length}
          </span>
          {activeTab === 'properties' && (
            <div className="absolute bottom-0 right-0 left-0 h-0.5 bg-brand-500 rounded-t-full" />
          )}
        </button>

        <button
          onClick={() => setActiveTab('locations')}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 transition-all relative ${
            activeTab === 'locations' ? 'text-brand-400' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <MapPin className="w-4 h-4" />
          <span>الهيكل الجغرافي والمشروعات</span>
          <span className="px-2 py-0.5 rounded-full text-xs bg-slate-800 text-slate-300 font-mono">
            {governorates.length} محافظات / {cities.length} مناطق
          </span>
          {activeTab === 'locations' && (
            <div className="absolute bottom-0 right-0 left-0 h-0.5 bg-brand-500 rounded-t-full" />
          )}
        </button>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* TAB A: PROPERTIES & INVENTORY WORKSPACE */}
      {/* --------------------------------------------------------------------- */}
      {activeTab === 'properties' && (
        <div className="space-y-5">
          {/* Geographic Hierarchy Selector Bar */}
          <div className="bg-slate-900 border border-slate-800 p-4 rounded-xl space-y-4">
            {/* Level 1: Governorates */}
            <div>
              <div className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-brand-400" />
                <span>المحافظة:</span>
              </div>
              <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
                <button
                  onClick={() => {
                    setSelectedGovId('');
                    setSelectedCityId('');
                  }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium shrink-0 transition-all ${
                    selectedGovId === ''
                      ? 'bg-brand-600 text-white shadow-md shadow-brand-600/20'
                      : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  كافة المحافظات
                </button>
                {governorates.map((gov) => (
                  <button
                    key={gov.id}
                    onClick={() => {
                      setSelectedGovId(gov.id);
                      setSelectedCityId('');
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium shrink-0 transition-all ${
                      selectedGovId === gov.id
                        ? 'bg-brand-600 text-white shadow-md shadow-brand-600/20'
                        : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                    }`}
                  >
                    {gov.name_ar}
                  </button>
                ))}
              </div>
            </div>

            {/* Level 2: Areas & Cities */}
            <div>
              <div className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1.5">
                <ChevronRight className="w-3.5 h-3.5 text-emerald-400" />
                <span>المنطقة / المدينة:</span>
              </div>
              <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
                <button
                  onClick={() => setSelectedCityId('')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium shrink-0 transition-all ${
                    selectedCityId === ''
                      ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                      : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  كافة المناطق
                </button>
                {availableCities.map((city) => (
                  <button
                    key={city.id}
                    onClick={() => setSelectedCityId(city.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium shrink-0 transition-all ${
                      selectedCityId === city.id
                        ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
                        : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                    }`}
                  >
                    {city.name_ar}
                  </button>
                ))}
              </div>
            </div>

            {/* Level 3: Projects vs Independent Units */}
            <div>
              <div className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                <span>المشروع التابع له:</span>
              </div>
              <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
                <button
                  onClick={() => setSelectedProjectId('')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium shrink-0 transition-all ${
                    selectedProjectId === ''
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                      : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  الكل (المشروعات والعقارات المستقلة)
                </button>
                <button
                  onClick={() => setSelectedProjectId('independent')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium shrink-0 transition-all ${
                    selectedProjectId === 'independent'
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                      : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  🏡 عقارات مستقلة بدون مشروع
                </button>
                {availableProjects.map((proj) => (
                  <button
                    key={proj.id}
                    onClick={() => setSelectedProjectId(proj.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium shrink-0 transition-all ${
                      selectedProjectId === proj.id
                        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                        : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                    }`}
                  >
                    {proj.name} ({proj.available_units || 0} متاح)
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Search & Filter Toolbar */}
          <div className="flex flex-col md:flex-row gap-3 items-center justify-between bg-slate-900 border border-slate-800 p-3 rounded-xl">
            <form onSubmit={handleSearchSubmit} className="relative flex-1 w-full">
              <Search className="w-4 h-4 text-slate-400 absolute right-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="ابحث برقم الوحدة، اسم المشروع، أو الموقع..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="input input-sm pr-9 text-xs w-full bg-slate-950 border-slate-800"
              />
            </form>

            <div className="flex items-center gap-2 flex-wrap w-full md:w-auto">
              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="input input-sm text-xs bg-slate-950 border-slate-800 text-slate-300"
              >
                <option value="">كافة الحالات</option>
                <option value="AVAILABLE">متاح للبيع</option>
                <option value="RESERVED">محجوز</option>
                <option value="SOLD">تم البيع</option>
                <option value="ARCHIVED">مؤرشف</option>
              </select>

              {/* Type Filter */}
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="input input-sm text-xs bg-slate-950 border-slate-800 text-slate-300"
              >
                <option value="">كافة أنواع العقار</option>
                <option value="Apartment">شقة (Apartment)</option>
                <option value="Villa">فيلا (Villa)</option>
                <option value="Duplex">دوبلكس (Duplex)</option>
                <option value="Townhouse">تاون هاوس (Townhouse)</option>
                <option value="Penthouse">بنتهاوس (Penthouse)</option>
                <option value="Studio">استوديو (Studio)</option>
              </select>

              {/* Include Archived Checkbox */}
              <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer select-none px-2 py-1 bg-slate-950 rounded-lg border border-slate-800">
                <input
                  type="checkbox"
                  checked={includeArchived}
                  onChange={(e) => setIncludeArchived(e.target.checked)}
                  className="rounded border-slate-700 text-brand-500 focus:ring-0"
                />
                <span>عرض المؤرشف</span>
              </label>

              {(search || statusFilter || typeFilter || selectedGovId || selectedCityId || selectedProjectId !== '') && (
                <button
                  onClick={() => {
                    setSearch('');
                    setStatusFilter('');
                    setTypeFilter('');
                    setSelectedGovId('');
                    setSelectedCityId('');
                    setSelectedProjectId('');
                  }}
                  className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded-lg text-xs"
                  title="إلغاء الفلاتر"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* ----------------------------------------------------------------- */}
          {/* Property Cards Grid */}
          {/* ----------------------------------------------------------------- */}
          {loading ? (
            <div className="py-24 text-center text-slate-400 text-xs animate-pulse">
              جاري تحميل الوحدات والمخزون العقاري...
            </div>
          ) : properties.length === 0 ? (
            <div className="py-20 text-center bg-slate-900 border border-slate-800 rounded-2xl">
              <Home className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-slate-300">لا توجد وحدات عقارية مطابقة</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                لم يتم العثور على وحدات تطابق معايير الفلترة أو البحث المحددة. جرب توسيع نطاق البحث أو إضافة وحدة جديدة.
              </p>
              {isManager && (
                <button
                  onClick={openCreatePropertyModal}
                  className="btn btn-primary mt-4 text-xs py-2 px-4 inline-flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  <span>إضافة أول وحدة</span>
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {properties.map((prop) => {
                const photosCount = prop.images?.length || 0;
                const videosCount = prop.videos?.length || 0;
                return (
                  <div
                    key={prop.id}
                    className={`bg-slate-900 border rounded-2xl overflow-hidden shadow-lg transition-all duration-200 hover:border-slate-700 flex flex-col ${
                      prop.is_archived ? 'border-slate-800/60 opacity-75' : 'border-slate-800'
                    }`}
                  >
                    {/* Property Card Image Header */}
                    <div className="relative h-44 bg-slate-950 overflow-hidden group">
                      {prop.primary_image_url ? (
                        <img
                          src={prop.primary_image_url}
                          alt={prop.unit_number}
                          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                        />
                      ) : (
                        <div className="w-full h-full flex flex-col items-center justify-center text-slate-600 bg-gradient-to-b from-slate-900 to-slate-950">
                          <Home className="w-12 h-12 stroke-[1.2]" />
                          <span className="text-xs mt-2 text-slate-500">لا توجد صورة رئيسية</span>
                        </div>
                      )}

                      {/* Top Badges */}
                      <div className="absolute top-3 right-3 left-3 flex items-center justify-between pointer-events-none">
                        {getStatusBadge(prop.availability_status, prop.is_archived)}
                        <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-900/80 backdrop-blur text-white border border-slate-700/50">
                          {prop.property_type}
                        </span>
                      </div>

                      {/* Media Badges */}
                      <div className="absolute bottom-3 left-3 flex items-center gap-1.5 pointer-events-none">
                        {photosCount > 0 && (
                          <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-900/80 backdrop-blur text-slate-200 border border-slate-700/50 flex items-center gap-1">
                            <ImageIcon className="w-3 h-3 text-brand-400" />
                            {photosCount}
                          </span>
                        )}
                        {videosCount > 0 && (
                          <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-900/80 backdrop-blur text-slate-200 border border-slate-700/50 flex items-center gap-1">
                            <VideoIcon className="w-3 h-3 text-rose-400" />
                            {videosCount}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Property Card Content */}
                    <div className="p-4 flex-1 flex flex-col justify-between space-y-3">
                      <div>
                        {/* Title & Project */}
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h3 className="font-bold text-white text-base">
                              {prop.title || `${prop.property_type} - ${prop.unit_number}`}
                            </h3>
                            <div className="flex items-center gap-1.5 text-xs text-brand-400 mt-0.5">
                              <Building2 className="w-3.5 h-3.5" />
                              <span>{prop.project_name || 'عقار مستقل'}</span>
                            </div>
                          </div>
                          <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                            #{prop.unit_number}
                          </span>
                        </div>

                        {/* Location */}
                        <div className="flex items-center gap-1 text-xs text-slate-400 mt-2">
                          <MapPin className="w-3.5 h-3.5 text-slate-500" />
                          <span>{prop.location} ({prop.city})</span>
                        </div>

                        {/* Specs Grid */}
                        <div className="grid grid-cols-3 gap-2 mt-3 pt-3 border-t border-slate-800/80 text-xs text-slate-300">
                          <div className="flex flex-col">
                            <span className="text-[10px] text-slate-500">المساحة</span>
                            <span className="font-semibold">{prop.area} م²</span>
                          </div>
                          <div className="flex flex-col">
                            <span className="text-[10px] text-slate-500">الغرف</span>
                            <span className="font-semibold">{prop.bedrooms} نوم / {prop.bathrooms} حمام</span>
                          </div>
                          <div className="flex flex-col">
                            <span className="text-[10px] text-slate-500">الدور</span>
                            <span className="font-semibold">{prop.floor} ({prop.view})</span>
                          </div>
                        </div>

                        {/* Price Details */}
                        <div className="mt-3.5 pt-3 border-t border-slate-800 flex items-baseline justify-between">
                          <div>
                            <div className="text-[11px] text-slate-400">السعر الإجمالي:</div>
                            <div className="text-base font-bold text-emerald-400">
                              {prop.total_price.toLocaleString()} <span className="text-xs font-normal text-slate-400">{prop.currency}</span>
                            </div>
                          </div>
                          {prop.down_payment > 0 && (
                            <div className="text-left">
                              <div className="text-[10px] text-slate-500">المقدم:</div>
                              <div className="text-xs font-semibold text-slate-300">
                                {prop.down_payment.toLocaleString()} {prop.currency}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Card Action Buttons */}
                      <div className="pt-3 border-t border-slate-800 flex items-center justify-between gap-1.5">
                        <button
                          onClick={() => setDetailsProperty(prop)}
                          className="btn btn-sm bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 flex-1 flex items-center justify-center gap-1 text-xs"
                        >
                          <Eye className="w-3.5 h-3.5 text-slate-400" />
                          <span>التفاصيل</span>
                        </button>

                        <button
                          onClick={() => setMediaProperty(prop)}
                          className="btn btn-sm bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 flex items-center justify-center gap-1 text-xs px-2.5"
                          title="الصور والفيديوهات"
                        >
                          <ImageIcon className="w-3.5 h-3.5 text-brand-400" />
                          <span>الوسائط</span>
                        </button>

                        {isManager && (
                          <>
                            <button
                              onClick={() => openEditPropertyModal(prop)}
                              className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded-lg"
                              title="تعديل بيانات الوحدة"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </button>

                            <button
                              onClick={() => handleToggleArchiveProperty(prop)}
                              className={`p-1.5 hover:bg-slate-800 rounded-lg ${
                                prop.is_archived ? 'text-amber-400' : 'text-slate-400 hover:text-rose-400'
                              }`}
                              title={prop.is_archived ? 'استعادة الوحدة' : 'أرشفة الوحدة'}
                            >
                              {prop.is_archived ? (
                                <RotateCcw className="w-3.5 h-3.5" />
                              ) : (
                                <Archive className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* TAB B: GEOGRAPHIC HIERARCHY & PROJECTS MANAGEMENT */}
      {/* --------------------------------------------------------------------- */}
      {activeTab === 'locations' && (
        <div className="space-y-6">
          {/* Projects Section */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-indigo-400" />
                <h2 className="text-base font-bold text-white">المشروعات العقارية المسجلة</h2>
              </div>
              {isManager && (
                <button
                  onClick={() => {
                    setEditingProjectId(null);
                    setProjForm({ name: '', developer: '', location: '', project_type: 'Residential', status: 'Under Construction', description: '' });
                    setProjectModalOpen(true);
                  }}
                  className="btn btn-sm btn-primary text-xs flex items-center gap-1.5"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>مشروع جديد</span>
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((proj) => (
                <div
                  key={proj.id}
                  className={`p-4 rounded-xl border bg-slate-950 flex flex-col justify-between ${
                    proj.is_archived ? 'border-slate-800 opacity-60' : 'border-slate-800'
                  }`}
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="font-bold text-white text-sm">{proj.name}</h3>
                      {proj.is_archived && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">مؤرشف</span>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">المطور: {proj.developer}</div>
                    <div className="text-xs text-slate-400">الموقع: {proj.location}</div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-900 flex items-center justify-between">
                    <span className="text-xs text-brand-400 font-medium">
                      {proj.available_units || 0} وحدات متاحة
                    </span>

                    {isManager && (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleToggleArchiveProject(proj)}
                          className="p-1 text-slate-400 hover:text-slate-200 rounded"
                          title={proj.is_archived ? 'استعادة' : 'أرشفة'}
                        >
                          {proj.is_archived ? <RotateCcw className="w-3.5 h-3.5" /> : <Archive className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Nested Geographic Hierarchy Tree */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MapPin className="w-5 h-5 text-emerald-400" />
                <h2 className="text-base font-bold text-white">الهيكل الجغرافي (محافظات ← مناطق/مدن ← أحياء)</h2>
              </div>
              {isManager && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => openLocationModal('governorate')}
                    className="btn btn-sm bg-slate-800 text-slate-200 border-slate-700 text-xs flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>محافظة</span>
                  </button>
                  <button
                    onClick={() => openLocationModal('city')}
                    className="btn btn-sm bg-slate-800 text-slate-200 border-slate-700 text-xs flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>مدينة / منطقة</span>
                  </button>
                  <button
                    onClick={() => openLocationModal('district')}
                    className="btn btn-sm bg-slate-800 text-slate-200 border-slate-700 text-xs flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>حي فرعي</span>
                  </button>
                </div>
              )}
            </div>

            <div className="space-y-4">
              {hierarchy.map((gov) => (
                <div key={gov.id} className="border border-slate-800 rounded-xl bg-slate-950/60 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-brand-500" />
                      <span className="font-bold text-white text-sm">{gov.name_ar}</span>
                      <span className="text-xs text-slate-500 font-mono">({gov.name_en})</span>
                    </div>
                    <span className="text-xs text-slate-400">
                      {gov.cities?.length || 0} مناطق تابعة
                    </span>
                  </div>

                  {/* Cities / Areas */}
                  <div className="mr-4 space-y-2.5 border-r border-slate-800 pr-3">
                    {gov.cities?.map((c) => (
                      <div key={c.id} className="bg-slate-900/80 p-3 rounded-lg border border-slate-800/80 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-xs text-slate-200">{c.name_ar} ({c.name_en})</span>
                          <span className="text-[11px] text-emerald-400 font-mono">
                            {c.districts?.length || 0} أحياء فرعية
                          </span>
                        </div>

                        {/* Sub Districts */}
                        {c.districts && c.districts.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {c.districts.map((d) => (
                              <span
                                key={d.id}
                                className="px-2 py-0.5 rounded text-[11px] bg-slate-800/80 text-slate-300 border border-slate-700/50"
                              >
                                {d.name_ar} ({d.properties_count || 0} وحدات)
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 4. MODALS & DRAWERS */}
      {/* --------------------------------------------------------------------- */}

      {/* A. Property Details Modal */}
      {detailsProperty && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div>
                <h3 className="text-lg font-bold text-white">
                  {detailsProperty.title || `${detailsProperty.property_type} - ${detailsProperty.unit_number}`}
                </h3>
                <div className="text-xs text-brand-400 mt-0.5">
                  {detailsProperty.project_name || 'عقار مستقل'} - {detailsProperty.location}
                </div>
              </div>
              <button
                onClick={() => setDetailsProperty(null)}
                className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Media Gallery in Details */}
            {detailsProperty.primary_image_url && (
              <div className="h-60 rounded-xl overflow-hidden bg-slate-950 border border-slate-800">
                <img
                  src={detailsProperty.primary_image_url}
                  alt={detailsProperty.unit_number}
                  className="w-full h-full object-cover"
                />
              </div>
            )}

            {/* Specs & Pricing Details */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs bg-slate-950 p-4 rounded-xl border border-slate-800">
              <div>
                <span className="text-slate-500">المساحة:</span>
                <p className="font-bold text-white text-sm">{detailsProperty.area} م²</p>
              </div>
              <div>
                <span className="text-slate-500">الغرف / الحمامات:</span>
                <p className="font-bold text-white text-sm">{detailsProperty.bedrooms} نوم / {detailsProperty.bathrooms} حمام</p>
              </div>
              <div>
                <span className="text-slate-500">الدور والإطلالة:</span>
                <p className="font-bold text-white text-sm">{detailsProperty.floor} ({detailsProperty.view})</p>
              </div>
              <div>
                <span className="text-slate-500">التشطيب والاستلام:</span>
                <p className="font-bold text-white text-sm">{detailsProperty.finishing_status} ({detailsProperty.delivery_date})</p>
              </div>
            </div>

            <div className="p-4 bg-emerald-500/5 border border-emerald-500/20 rounded-xl flex items-center justify-between">
              <div>
                <span className="text-xs text-emerald-400">السعر الإجمالي:</span>
                <h4 className="text-xl font-bold text-emerald-400">
                  {detailsProperty.total_price.toLocaleString()} {detailsProperty.currency}
                </h4>
              </div>
              <div className="text-left text-xs text-slate-300">
                <div>نظام السداد: {detailsProperty.installment_plan}</div>
                {detailsProperty.down_payment > 0 && (
                  <div>المقدم: {detailsProperty.down_payment.toLocaleString()} {detailsProperty.currency}</div>
                )}
              </div>
            </div>

            {detailsProperty.description && (
              <div>
                <span className="text-xs font-semibold text-slate-400">الوصف والملاحظات:</span>
                <p className="text-xs text-slate-300 mt-1 leading-relaxed bg-slate-950 p-3 rounded-lg border border-slate-800">
                  {detailsProperty.description}
                </p>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => {
                  const p = detailsProperty;
                  setDetailsProperty(null);
                  setMediaProperty(p);
                }}
                className="btn bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 text-xs py-2 px-3.5 flex items-center gap-1.5"
              >
                <ImageIcon className="w-4 h-4 text-brand-400" />
                <span>إدارة الوسائط ({detailsProperty.images?.length || 0} صور / {detailsProperty.videos?.length || 0} فيديو)</span>
              </button>
              <button
                onClick={() => setDetailsProperty(null)}
                className="btn btn-secondary text-xs py-2 px-4"
              >
                إغلاق
              </button>
            </div>
          </div>
        </div>
      )}

      {/* B. Property Media Modal (Photos & Videos) */}
      {mediaProperty && (
        <PropertyMediaManagerModal
          property={mediaProperty}
          onClose={() => setMediaProperty(null)}
          onUpdated={fetchAllData}
        />
      )}

      {/* C. Create / Edit Property Modal */}
      {propertyModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-brand-400" />
                <h3 className="text-lg font-bold text-white">
                  {editingPropertyId ? 'تعديل بيانات الوحدة العقارية' : 'إضافة وحدة عقارية جديدة'}
                </h3>
              </div>
              <button
                onClick={() => setPropertyModalOpen(false)}
                className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-xl flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handlePropertySubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Title */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">عنوان أو اسم تسويقي للوحدة:</label>
                  <input
                    type="text"
                    value={propForm.title}
                    onChange={(e) => setPropForm({ ...propForm, title: e.target.value })}
                    placeholder="مثال: شقة 3 غرف فيو بحري بالنرجس"
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                  />
                </div>

                {/* Unit Number */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">رقم أو كود الوحدة *:</label>
                  <input
                    type="text"
                    required
                    value={propForm.unit_number}
                    onChange={(e) => setPropForm({ ...propForm, unit_number: e.target.value })}
                    placeholder="مثال: A-204"
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                  />
                </div>

                {/* Project Selection (Nullable for Independent Properties) */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">المشروع التابع له:</label>
                  <select
                    value={propForm.project_id}
                    onChange={(e) => setPropForm({ ...propForm, project_id: e.target.value })}
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800 text-slate-200"
                  >
                    <option value="">عقار مستقل (بدون مشروع)</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>{p.name} ({p.location})</option>
                    ))}
                  </select>
                </div>

                {/* Property Type */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">نوع العقار:</label>
                  <select
                    value={propForm.property_type}
                    onChange={(e) => setPropForm({ ...propForm, property_type: e.target.value })}
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800 text-slate-200"
                  >
                    <option value="Apartment">شقة (Apartment)</option>
                    <option value="Villa">فيلا (Villa)</option>
                    <option value="Duplex">دوبلكس (Duplex)</option>
                    <option value="Townhouse">تاون هاوس (Townhouse)</option>
                    <option value="Penthouse">بنتهاوس (Penthouse)</option>
                    <option value="Studio">استوديو (Studio)</option>
                    <option value="Office">مكتب إداري (Office)</option>
                    <option value="Commercial">تجاري (Commercial)</option>
                  </select>
                </div>

                {/* Governorate & City */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">المحافظة:</label>
                  <select
                    value={propForm.governorate_id}
                    onChange={(e) => setPropForm({ ...propForm, governorate_id: e.target.value })}
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800 text-slate-200"
                  >
                    <option value="">اختر المحافظة...</option>
                    {governorates.map((g) => (
                      <option key={g.id} value={g.id}>{g.name_ar}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">المنطقة / المدينة:</label>
                  <input
                    type="text"
                    value={propForm.location}
                    onChange={(e) => setPropForm({ ...propForm, location: e.target.value })}
                    placeholder="مثال: التجمع الخامس، الشيخ زايد"
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                  />
                </div>

                {/* Financial Details */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">السعر الإجمالي (EGP) *:</label>
                  <input
                    type="number"
                    required
                    min="1"
                    value={propForm.total_price}
                    onChange={(e) => setPropForm({ ...propForm, total_price: e.target.value })}
                    placeholder="مثال: 3500000"
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">المقدم (EGP):</label>
                  <input
                    type="number"
                    min="0"
                    value={propForm.down_payment}
                    onChange={(e) => setPropForm({ ...propForm, down_payment: e.target.value })}
                    placeholder="مثال: 350000"
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                  />
                </div>

                {/* Specs */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">المساحة (م²) *:</label>
                  <input
                    type="number"
                    required
                    min="1"
                    value={propForm.area}
                    onChange={(e) => setPropForm({ ...propForm, area: e.target.value })}
                    placeholder="مثال: 155"
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">الغرف:</label>
                    <input
                      type="number"
                      min="0"
                      value={propForm.bedrooms}
                      onChange={(e) => setPropForm({ ...propForm, bedrooms: e.target.value })}
                      className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1">الحمامات:</label>
                    <input
                      type="number"
                      min="0"
                      value={propForm.bathrooms}
                      onChange={(e) => setPropForm({ ...propForm, bathrooms: e.target.value })}
                      className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">حالة الوحدة:</label>
                  <select
                    value={propForm.availability_status}
                    onChange={(e) => setPropForm({ ...propForm, availability_status: e.target.value as PropertyStatus })}
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800 text-slate-200"
                  >
                    <option value="AVAILABLE">متاح للبيع (Available)</option>
                    <option value="RESERVED">محجوز (Reserved)</option>
                    <option value="SOLD">تم البيع (Sold)</option>
                    <option value="ARCHIVED">مؤرشف (Archived)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">نظام التقسيط:</label>
                  <input
                    type="text"
                    value={propForm.installment_plan}
                    onChange={(e) => setPropForm({ ...propForm, installment_plan: e.target.value })}
                    placeholder="مثال: 8 سنوات أقساط متساوية"
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">الوصف والمزايا:</label>
                <textarea
                  rows={3}
                  value={propForm.description}
                  onChange={(e) => setPropForm({ ...propForm, description: e.target.value })}
                  placeholder="اكتب مواصفات وتفاصيل إضافية عن الوحدة..."
                  className="input text-xs w-full bg-slate-950 border-slate-800 py-2"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setPropertyModalOpen(false)}
                  className="btn btn-secondary text-xs py-2 px-4"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="btn btn-primary text-xs py-2 px-5 flex items-center gap-1.5"
                >
                  {formSubmitting ? 'جاري الحفظ...' : (editingPropertyId ? 'حفظ التعديلات' : 'تسجيل الوحدة')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* D. Create Project Modal */}
      {projectModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="font-bold text-white text-base">إضافة مشروع عقاري جديد</h3>
              <button onClick={() => setProjectModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-xl">
                {formError}
              </div>
            )}

            <form onSubmit={handleProjectSubmit} className="space-y-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">اسم المشروع *:</label>
                <input
                  type="text"
                  required
                  value={projForm.name}
                  onChange={(e) => setProjForm({ ...projForm, name: e.target.value })}
                  placeholder="مثال: كمبوند بالم هيلز"
                  className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">المطور العقاري:</label>
                <input
                  type="text"
                  value={projForm.developer}
                  onChange={(e) => setProjForm({ ...projForm, developer: e.target.value })}
                  placeholder="مثال: بالم هيلز للتعمير"
                  className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">الموقع:</label>
                <input
                  type="text"
                  value={projForm.location}
                  onChange={(e) => setProjForm({ ...projForm, location: e.target.value })}
                  placeholder="مثال: 6 أكتوبر"
                  className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setProjectModalOpen(false)}
                  className="btn btn-secondary text-xs py-2 px-3.5"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="btn btn-primary text-xs py-2 px-4"
                >
                  {formSubmitting ? 'جاري الحفظ...' : 'حفظ المشروع'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* E. Location Modal (Gov / City / District) */}
      {locationModalType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="font-bold text-white text-base">
                {locationModalType === 'governorate' && 'إضافة محافظة جديدة'}
                {locationModalType === 'city' && 'إضافة مدينة أو منطقة جديدة'}
                {locationModalType === 'district' && 'إضافة حي فرعي جديد'}
              </h3>
              <button onClick={() => setLocationModalType(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            {formError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-xl">
                {formError}
              </div>
            )}

            <form onSubmit={handleLocationSubmit} className="space-y-3">
              {locationModalType === 'city' && (
                <div>
                  <label className="block text-xs text-slate-400 mb-1">المحافظة التابعة لها:</label>
                  <select
                    value={locForm.governorate_id}
                    onChange={(e) => setLocForm({ ...locForm, governorate_id: parseInt(e.target.value) })}
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800 text-slate-200"
                  >
                    {governorates.map((g) => (
                      <option key={g.id} value={g.id}>{g.name_ar}</option>
                    ))}
                  </select>
                </div>
              )}

              {locationModalType === 'district' && (
                <div>
                  <label className="block text-xs text-slate-400 mb-1">المنطقة أو المدينة التابع لها:</label>
                  <select
                    value={locForm.city_id}
                    onChange={(e) => setLocForm({ ...locForm, city_id: parseInt(e.target.value) })}
                    className="input input-sm text-xs w-full bg-slate-950 border-slate-800 text-slate-200"
                  >
                    {cities.map((c) => (
                      <option key={c.id} value={c.id}>{c.name_ar}</option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-xs text-slate-400 mb-1">الاسم بالعربية *:</label>
                <input
                  type="text"
                  required
                  value={locForm.name_ar}
                  onChange={(e) => setLocForm({ ...locForm, name_ar: e.target.value })}
                  placeholder="مثال: التجمع الخامس"
                  className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">الاسم بالإنجليزية:</label>
                <input
                  type="text"
                  value={locForm.name_en}
                  onChange={(e) => setLocForm({ ...locForm, name_en: e.target.value })}
                  placeholder="مثال: New Cairo"
                  className="input input-sm text-xs w-full bg-slate-950 border-slate-800"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setLocationModalType(null)}
                  className="btn btn-secondary text-xs py-2 px-3.5"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={formSubmitting}
                  className="btn btn-primary text-xs py-2 px-4"
                >
                  {formSubmitting ? 'جاري الحفظ...' : 'حفظ'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};


// -----------------------------------------------------------------------------
// Sub-Component: Property Media Manager Modal (Photos & Videos)
// -----------------------------------------------------------------------------
interface PropertyMediaManagerModalProps {
  property: Property;
  onClose: () => void;
  onUpdated: () => void;
}

const PropertyMediaManagerModal: React.FC<PropertyMediaManagerModalProps> = ({
  property,
  onClose,
  onUpdated
}) => {
  const { user } = useAuth();
  const isManager = ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER'].includes(user?.role || '');

  const [activeTab, setActiveTab] = useState<'photos' | 'videos'>('photos');

  // Images state
  const [images, setImages] = useState<PropertyImage[]>([]);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [photoCaption, setPhotoCaption] = useState('');
  const [photoIsPrimary, setPhotoIsPrimary] = useState(false);

  // Videos state
  const [videos, setVideos] = useState<PropertyVideo[]>([]);
  const [uploadingVideo, setUploadingVideo] = useState(false);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoTitle, setVideoTitle] = useState('');
  const [externalVideoUrl, setExternalVideoUrl] = useState('');
  const [externalVideoTitle, setExternalVideoTitle] = useState('');
  const [addingExternalVideo, setAddingExternalVideo] = useState(false);

  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const loadMedia = () => {
    Promise.all([
      api.get<PropertyImage[]>(`/properties/${property.id}/images`),
      api.get<PropertyVideo[]>(`/properties/${property.id}/videos`)
    ])
      .then(([imgs, vids]) => {
        setImages(imgs);
        setVideos(vids);
      })
      .catch((err) => setErrorMsg(err.message || 'فشل تحميل وسائط الوحدة'));
  };

  useEffect(() => {
    loadMedia();
  }, [property.id]);

  // Upload Photo
  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setPhotoFile(file);
      const reader = new FileReader();
      reader.onloadend = () => setPhotoPreview(reader.result as string);
      reader.readAsDataURL(file);
    }
  };

  const handleUploadPhoto = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!photoFile) return;
    setUploadingImage(true);
    setErrorMsg('');
    try {
      const formData = new FormData();
      formData.append('file', photoFile);
      if (photoCaption.trim()) formData.append('caption', photoCaption.trim());
      formData.append('is_primary', String(photoIsPrimary));

      await api.postForm(`/properties/${property.id}/images`, formData);
      setSuccessMsg('تم رفع الصورة بنجاح');
      setPhotoFile(null);
      setPhotoPreview(null);
      setPhotoCaption('');
      setPhotoIsPrimary(false);
      loadMedia();
      onUpdated();
      setTimeout(() => setSuccessMsg(''), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || 'فشل رفع الصورة');
    } finally {
      setUploadingImage(false);
    }
  };

  const handleDeletePhoto = async (imgId: number) => {
    if (!window.confirm('هل تريد حذف هذه الصورة؟')) return;
    try {
      await api.delete(`/properties/${property.id}/images/${imgId}`);
      loadMedia();
      onUpdated();
    } catch (err: any) {
      setErrorMsg(err.message || 'فشل حذف الصورة');
    }
  };

  const handleSetPrimaryPhoto = async (imgId: number) => {
    try {
      await api.put(`/properties/${property.id}/images/${imgId}/primary`);
      loadMedia();
      onUpdated();
    } catch (err: any) {
      setErrorMsg(err.message || 'فشل تحديد الصورة كصورة رئيسية');
    }
  };

  // Upload Video File
  const handleVideoFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.size > 50 * 1024 * 1024) {
        setErrorMsg('حجم ملف الفيديو يتجاوز الحد الأقصى المسموح (50 ميجابايت).');
        return;
      }
      setVideoFile(file);
      setErrorMsg('');
    }
  };

  const handleUploadVideoFile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!videoFile) return;
    setUploadingVideo(true);
    setErrorMsg('');
    try {
      const formData = new FormData();
      formData.append('file', videoFile);
      if (videoTitle.trim()) formData.append('title', videoTitle.trim());

      await api.postForm(`/properties/${property.id}/videos/upload`, formData);
      setSuccessMsg('تم رفع ملف الفيديو بنجاح');
      setVideoFile(null);
      setVideoTitle('');
      loadMedia();
      onUpdated();
      setTimeout(() => setSuccessMsg(''), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || 'فشل رفع الفيديو');
    } finally {
      setUploadingVideo(false);
    }
  };

  // Add External Video URL (YouTube, Drive, etc.)
  const handleAddExternalVideo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!externalVideoUrl.trim()) return;
    setAddingExternalVideo(true);
    setErrorMsg('');
    try {
      await api.post(`/properties/${property.id}/videos`, {
        video_url: externalVideoUrl.trim(),
        video_type: 'EXTERNAL',
        title: externalVideoTitle.trim() || 'رابط فيديو خارجي'
      });
      setSuccessMsg('تمت إضافة رابط الفيديو بنجاح');
      setExternalVideoUrl('');
      setExternalVideoTitle('');
      loadMedia();
      onUpdated();
      setTimeout(() => setSuccessMsg(''), 3000);
    } catch (err: any) {
      setErrorMsg(err.message || 'فشل إضافة رابط الفيديو');
    } finally {
      setAddingExternalVideo(false);
    }
  };

  const handleDeleteVideo = async (vidId: number) => {
    if (!window.confirm('هل تريد حذف هذا الفيديو؟')) return;
    try {
      await api.delete(`/properties/${property.id}/videos/${vidId}`);
      loadMedia();
      onUpdated();
    } catch (err: any) {
      setErrorMsg(err.message || 'فشل حذف الفيديو');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-5 shadow-2xl">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <ImageIcon className="w-5 h-5 text-brand-400" />
              <span>إدارة وسائط الوحدة #{property.unit_number}</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {property.title || `${property.property_type} - ${property.location}`}
            </p>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMsg && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs rounded-xl flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {successMsg && (
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs rounded-xl flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Media Type Sub-Tabs */}
        <div className="flex border-b border-slate-800 gap-4">
          <button
            onClick={() => setActiveTab('photos')}
            className={`pb-2.5 text-xs font-semibold flex items-center gap-1.5 transition-all relative ${
              activeTab === 'photos' ? 'text-brand-400' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ImageIcon className="w-4 h-4" />
            <span>الصور الفوتوغرافية ({images.length})</span>
            {activeTab === 'photos' && <div className="absolute bottom-0 right-0 left-0 h-0.5 bg-brand-500" />}
          </button>

          <button
            onClick={() => setActiveTab('videos')}
            className={`pb-2.5 text-xs font-semibold flex items-center gap-1.5 transition-all relative ${
              activeTab === 'videos' ? 'text-rose-400' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <VideoIcon className="w-4 h-4" />
            <span>الفيديوهات والعروض المرئية ({videos.length})</span>
            {activeTab === 'videos' && <div className="absolute bottom-0 right-0 left-0 h-0.5 bg-rose-500" />}
          </button>
        </div>

        {/* ----------------------------------------------------------------- */}
        {/* PHOTOS TAB */}
        {/* ----------------------------------------------------------------- */}
        {activeTab === 'photos' && (
          <div className="space-y-5">
            {isManager && (
              <form onSubmit={handleUploadPhoto} className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                <h4 className="text-xs font-bold text-slate-300">رفع صورة جديدة:</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handlePhotoSelect}
                      className="text-xs text-slate-400 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:bg-brand-600 file:text-white hover:file:bg-brand-700 cursor-pointer"
                    />
                    {photoPreview && (
                      <div className="mt-2 w-24 h-16 rounded border border-slate-800 overflow-hidden">
                        <img src={photoPreview} alt="Preview" className="w-full h-full object-cover" />
                      </div>
                    )}
                  </div>

                  <div>
                    <input
                      type="text"
                      placeholder="تعليق أو وصف الصورة (اختياري)..."
                      value={photoCaption}
                      onChange={(e) => setPhotoCaption(e.target.value)}
                      className="input input-sm text-xs w-full bg-slate-900 border-slate-800"
                    />
                    <label className="flex items-center gap-1.5 text-xs text-slate-400 mt-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={photoIsPrimary}
                        onChange={(e) => setPhotoIsPrimary(e.target.checked)}
                        className="rounded border-slate-700 text-brand-500 focus:ring-0"
                      />
                      <span>تعيين كصورة رئيسية للوحدة</span>
                    </label>
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={!photoFile || uploadingImage}
                    className="btn btn-primary text-xs py-1.5 px-3.5 flex items-center gap-1.5"
                  >
                    {uploadingImage ? 'جاري الرفع...' : 'رفع الصورة'}
                  </button>
                </div>
              </form>
            )}

            {/* Photos Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {images.map((img) => (
                <div key={img.id} className="relative rounded-xl overflow-hidden border border-slate-800 bg-slate-950 group">
                  <img src={img.image_url} alt={img.caption || ''} className="w-full h-32 object-cover" />
                  {img.is_primary && (
                    <span className="absolute top-2 right-2 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500 text-slate-950 shadow">
                      رئيسية
                    </span>
                  )}
                  {img.caption && (
                    <div className="p-2 text-[11px] text-slate-300 truncate bg-slate-900 border-t border-slate-800">
                      {img.caption}
                    </div>
                  )}
                  {isManager && (
                    <div className="absolute inset-0 bg-slate-950/70 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                      {!img.is_primary && (
                        <button
                          onClick={() => handleSetPrimaryPhoto(img.id)}
                          className="p-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg text-xs"
                          title="تعيين كرئيسية"
                        >
                          رئيسية
                        </button>
                      )}
                      <button
                        onClick={() => handleDeletePhoto(img.id)}
                        className="p-1.5 bg-rose-500/80 hover:bg-rose-500 text-white rounded-lg text-xs"
                        title="حذف الصورة"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* VIDEOS TAB */}
        {/* ----------------------------------------------------------------- */}
        {activeTab === 'videos' && (
          <div className="space-y-5">
            {isManager && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Option 1: File Upload */}
                <form onSubmit={handleUploadVideoFile} className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                  <h4 className="text-xs font-bold text-slate-300">رفع ملف فيديو (MP4/WebM حتى 50MB):</h4>
                  <input
                    type="file"
                    accept="video/mp4,video/webm,video/quicktime,video/x-matroska"
                    onChange={handleVideoFileSelect}
                    className="text-xs text-slate-400 file:mr-2 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:bg-rose-600 file:text-white hover:file:bg-rose-700 cursor-pointer w-full"
                  />
                  <input
                    type="text"
                    placeholder="عنوان الفيديو (مثال: جولة داخلية)..."
                    value={videoTitle}
                    onChange={(e) => setVideoTitle(e.target.value)}
                    className="input input-sm text-xs w-full bg-slate-900 border-slate-800"
                  />
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={!videoFile || uploadingVideo}
                      className="btn bg-rose-600 hover:bg-rose-500 text-white text-xs py-1.5 px-3.5"
                    >
                      {uploadingVideo ? 'جاري رفع الفيديو...' : 'رفع ملف الفيديو'}
                    </button>
                  </div>
                </form>

                {/* Option 2: External Video Link */}
                <form onSubmit={handleAddExternalVideo} className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                  <h4 className="text-xs font-bold text-slate-300">إضافة رابط خارجي (YouTube / Google Drive):</h4>
                  <input
                    type="url"
                    required
                    placeholder="https://www.youtube.com/watch?v=... أو رابط Drive"
                    value={externalVideoUrl}
                    onChange={(e) => setExternalVideoUrl(e.target.value)}
                    className="input input-sm text-xs w-full bg-slate-900 border-slate-800"
                  />
                  <input
                    type="text"
                    placeholder="عنوان الرابط..."
                    value={externalVideoTitle}
                    onChange={(e) => setExternalVideoTitle(e.target.value)}
                    className="input input-sm text-xs w-full bg-slate-900 border-slate-800"
                  />
                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={!externalVideoUrl.trim() || addingExternalVideo}
                      className="btn btn-primary text-xs py-1.5 px-3.5"
                    >
                      {addingExternalVideo ? 'جاري الإضافة...' : 'إضافة الرابط'}
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* Videos List */}
            <div className="space-y-3">
              {videos.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-500 bg-slate-950 rounded-xl border border-slate-800">
                  لا توجد مقاطع فيديو مسجلة لهذه الوحدة حتى الآن.
                </div>
              ) : (
                videos.map((vid) => (
                  <div key={vid.id} className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        <Play className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-white">{vid.title || 'Property Video'}</div>
                        <div className="text-[11px] text-slate-500 font-mono truncate max-w-md">{vid.video_url}</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {vid.video_type === 'UPLOAD' ? 'ملف مرفوع' : 'رابط خارجي'}
                      </span>
                      <a
                        href={vid.video_url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700 flex items-center gap-1 text-[11px]"
                      >
                        <ExternalLink className="w-3 h-3" />
                        <span>فتح</span>
                      </a>
                      {isManager && (
                        <button
                          onClick={() => handleDeleteVideo(vid.id)}
                          className="p-1.5 text-slate-400 hover:text-rose-400 rounded"
                          title="حذف الفيديو"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        <div className="flex justify-end pt-3 border-t border-slate-800">
          <button onClick={onClose} className="btn btn-secondary text-xs py-2 px-4">
            إغلاق
          </button>
        </div>
      </div>
    </div>
  );
};

