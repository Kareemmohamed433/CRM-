import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, Phone, Mail, MapPin, Calendar, Clock,
  Sparkles, CheckCircle2, AlertCircle, Building2, PhoneCall, Plus,
  ArrowLeftRight, ShieldCheck, Tag, FileText, Check, MessageCircle,
  Send, ThumbsUp, ThumbsDown, ExternalLink, History, MessageSquare
} from 'lucide-react';
import { api } from '../api/client';
import { Lead, PipelineStage, PriorityLevel, PropertyOffer, CustomerTimelineEvent } from '../types';
import { useAuth } from '../context/AuthContext';
import { UnitPickerModal } from '../components/modals/UnitPickerModal';
import { SendPropertyOfferModal } from '../components/modals/SendPropertyOfferModal';

export const LeadDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [updatingStage, setUpdatingStage] = useState(false);
  const [pendingStage, setPendingStage] = useState<'RESERVATION' | 'WON' | null>(null);
  const [transferModalOpen, setTransferModalOpen] = useState(false);
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [shareOfferModalOpen, setShareOfferModalOpen] = useState(false);

  // Tabs & Data state
  const [activeTab, setActiveTab] = useState<'TIMELINE' | 'OFFERS' | 'ACTIVITIES'>('TIMELINE');
  const [timeline, setTimeline] = useState<CustomerTimelineEvent[]>([]);
  const [propertyOffers, setPropertyOffers] = useState<PropertyOffer[]>([]);
  const [loadingTimeline, setLoadingTimeline] = useState(false);

  // Feedback Modal State
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [selectedOfferForFeedback, setSelectedOfferForFeedback] = useState<PropertyOffer | null>(null);
  const [feedbackText, setFeedbackText] = useState('');
  const [feedbackStatus, setFeedbackStatus] = useState<string>('ACCEPTED');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  // New activity state
  const [activityType, setActivityType] = useState('CALL');
  const [activitySummary, setActivitySummary] = useState('');
  const [activityOutcome, setActivityOutcome] = useState('');

  // Transfer state
  const [transferAgentId, setTransferAgentId] = useState('');
  const [transferReason, setTransferReason] = useState('Project Specialization');
  const [transferNotes, setTransferNotes] = useState('');
  const [companyUsers, setCompanyUsers] = useState<any[]>([]);

  const { isRtl, user } = useAuth();
  const navigate = useNavigate();

  const fetchLeadDetails = () => {
    setLoading(true);
    api.get<any>(`/leads/${id}`)
      .then((res) => {
        setData(res);
        loadTimelineAndOffers();
      })
      .catch((err) => {
        alert(err.message || 'فشل تحميل بيانات العميل');
        navigate('/leads');
      })
      .finally(() => setLoading(false));
  };

  const loadTimelineAndOffers = () => {
    setLoadingTimeline(true);
    Promise.all([
      api.get<CustomerTimelineEvent[]>(`/leads/${id}/timeline`),
      api.get<PropertyOffer[]>(`/leads/${id}/property-offers`)
    ])
      .then(([tl, offers]) => {
        setTimeline(tl);
        setPropertyOffers(offers);
      })
      .catch(console.error)
      .finally(() => setLoadingTimeline(false));
  };

  const handleRecordFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOfferForFeedback) return;
    setSubmittingFeedback(true);
    try {
      await api.post(`/property-offers/${selectedOfferForFeedback.id}/feedback`, {
        status: feedbackStatus,
        feedback: feedbackText
      });
      setFeedbackModalOpen(false);
      setSelectedOfferForFeedback(null);
      setFeedbackText('');
      loadTimelineAndOffers();
    } catch (err: any) {
      alert(err.message || 'فشل تسجيل رد العميل');
    } finally {
      setSubmittingFeedback(false);
    }
  };

  useEffect(() => {
    fetchLeadDetails();
    // Load company users for transfer dropdown
    api.get<any[]>('/users').then(setCompanyUsers).catch(console.error);
  }, [id]);

  const sendStage = async (newStage: string, propertyId?: number) => {
    await api.patch(`/leads/${id}/stage`, {
      pipeline_stage: newStage,
      property_id: propertyId,
      notes: `تغيير المرحلة إلى ${newStage}`
    });
    fetchLeadDetails();
  };

  const handleStageChange = async (newStage: string) => {
    // Reservation / Won need a unit: ask for it unless the lead already holds one
    const heldUnit = (data?.lead as any)?.reserved_property;
    if ((newStage === 'RESERVATION' || newStage === 'WON') && !heldUnit) {
      setPendingStage(newStage);
      return;
    }
    setUpdatingStage(true);
    try {
      await sendStage(newStage);
    } catch (err: any) {
      alert(`فشل تغيير المرحلة: ${err.message}`);
    } finally {
      setUpdatingStage(false);
    }
  };

  const handleAddActivity = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/activities', {
        lead_id: parseInt(id!),
        activity_type: activityType,
        summary: activitySummary,
        outcome: activityOutcome,
      });
      setActivityModalOpen(false);
      setActivitySummary('');
      setActivityOutcome('');
      fetchLeadDetails();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleRequestTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/transfers', {
        lead_id: parseInt(id!),
        requested_owner_id: parseInt(transferAgentId),
        reason: transferReason,
        notes: transferNotes,
      });
      setTransferModalOpen(false);
      alert('تم إرسال طلب نقل العميل بنجاح إلى الإدارة للمراجعة والاعتماد.');
      fetchLeadDetails();
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (loading || !data) {
    return (
      <div className="py-24 text-center text-slate-400 text-xs animate-pulse">
        جاري تحميل السجل الكامل للعميل...
      </div>
    );
  }

  const lead: Lead = data.lead;
  const activities = data.activities || [];
  const followups = data.followups || [];
  const alternatives = data.recommended_alternatives || [];
  const reservedUnit = (lead as any).reserved_property as any | undefined;
  const dealClosed = lead.pipeline_stage === 'WON' || lead.pipeline_stage === 'LOST';

  return (
    <div className="space-y-6 text-start">
      {/* Back button */}
      <div>
        <button
          onClick={() => navigate('/leads')}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white transition-colors"
        >
          {isRtl ? <ArrowRight className="w-4 h-4" /> : <ArrowLeft className="w-4 h-4" />}
          <span>العودة إلى قائمة العملاء</span>
        </button>
      </div>

      {/* Main Lead Header Card */}
      <div className="p-6 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl relative overflow-hidden">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 flex items-center justify-center font-black text-xl text-white shadow-lg shrink-0">
              {lead.full_name.charAt(0)}
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h1 className="text-xl sm:text-2xl font-black text-white">{lead.full_name}</h1>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                  Lead #{lead.id}
                </span>
                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${lead.priority === 'URGENT' ? 'bg-rose-500/20 text-rose-300 border-rose-500/30' : 'bg-slate-800 text-slate-300 border-slate-700'
                  }`}>
                  أولوية: {lead.priority}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400 mt-2">
                <span className="flex items-center gap-1.5 text-slate-200">
                  <Phone className="w-3.5 h-3.5 text-brand-400" />
                  {lead.phone}
                </span>
                {lead.email && (
                  <span className="flex items-center gap-1.5 text-slate-200">
                    <Mail className="w-3.5 h-3.5 text-brand-400" />
                    {lead.email}
                  </span>
                )}
                <span className="flex items-center gap-1.5">
                  المستشار: <strong className="text-white">{lead.assigned_agent_name || 'غير مسند'}</strong>
                </span>
              </div>
            </div>
          </div>

          {/* Stage Switcher & Quick Actions */}
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <label className="block text-[10px] text-slate-400 font-semibold mb-1">مرحلة البيع الحالية:</label>
              <select
                value={lead.pipeline_stage}
                disabled={updatingStage}
                onChange={(e) => handleStageChange(e.target.value)}
                className="bg-slate-800 border border-brand-500/40 text-xs font-bold rounded-xl px-3 py-2 text-brand-300 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
              >
                <option value="NEW">عميل جديد (NEW)</option>
                <option value="CONTACTED">تم التواصل (CONTACTED)</option>
                <option value="QUALIFIED">مؤهل (QUALIFIED)</option>
                <option value="VISIT_SCHEDULED">معاينة مجدولة (VISIT_SCHEDULED)</option>
                <option value="VISIT_COMPLETED">تمت المعاينة (VISIT_COMPLETED)</option>
                <option value="NEGOTIATION">مرحلة التفاوض (NEGOTIATION)</option>
                <option value="RESERVATION">حجز مبدئي (RESERVATION)</option>
                <option value="WON">صفقة مغلقة بنجاح (WON)</option>
                <option value="LOST">صفقة خاسرة (LOST)</option>
              </select>
            </div>

            <button
              onClick={() => setShareOfferModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition-all shadow-md mt-4"
            >
              <MessageCircle className="w-3.5 h-3.5" />
              <span>إرسال عرض عبر واتساب</span>
            </button>

            <button
              onClick={() => setActivityModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-md mt-4"
            >
              <PhoneCall className="w-3.5 h-3.5" />
              <span>تسجيل مكالمة / نشاط</span>
            </button>

            <button
              onClick={() => setTransferModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all mt-4"
            >
              <ArrowLeftRight className="w-3.5 h-3.5 text-amber-400" />
              <span>طلب نقل العميل</span>
            </button>
          </div>
        </div>

        {/* AI Score Factors Bar */}
        <div className="mt-6 pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="font-bold text-amber-400 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4" />
              نقاط الجاهزية الذكية: {lead.score} / 100
            </span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-300">
              العوامل: {lead.score_factors?.map(f => f.factor).join(' • ') || 'بيانات أولية'}
            </span>
          </div>

          {lead.next_followup_date && (
            <span className="text-slate-300 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-brand-400" />
              المتابعة القادمة: {new Date(lead.next_followup_date).toLocaleDateString('ar-EG')}
            </span>
          )}
        </div>
      </div>

      {/* Grid: Preferences & Alternatives vs Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Requirements & Alternatives */}
        <div className="space-y-6">
          {/* Customer Preferences Card */}
          <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
            <h3 className="font-bold text-sm text-white flex items-center gap-2">
              <Building2 className="w-4 h-4 text-brand-400" />
              متطلبات وتفضيلات العميل
            </h3>

            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">سقف الميزانية:</span>
                <span className="font-bold text-white">
                  {lead.budget_max > 0 ? `${lead.budget_max.toLocaleString()} ج.م` : 'غير محدد'}
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">الموقع المفضل:</span>
                <span className="font-semibold text-slate-200">{lead.preferred_location || 'التجمع الخامس'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">نوع العقار:</span>
                <span className="font-semibold text-slate-200">{lead.property_type || 'شقة سكني'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">عدد الغرف:</span>
                <span className="font-semibold text-slate-200">{lead.bedrooms || 2} غرف نوم</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">أفق الشراء:</span>
                <span className="font-semibold text-emerald-400">{lead.purchase_timeline}</span>
              </div>
              {lead.notes && (
                <div className="pt-2">
                  <span className="text-slate-400 block mb-1">ملاحظات العميل:</span>
                  <p className="text-slate-300 p-2.5 rounded-xl bg-slate-800/40 border border-slate-800 text-[11px] leading-relaxed">
                    {lead.notes}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Unit held by this lead (reserved / sold) */}
          {reservedUnit && (
            <div className="p-5 rounded-3xl bg-slate-900 border border-teal-500/40 shadow-xl space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-sm text-white flex items-center gap-1.5">
                  <Building2 className="w-4 h-4 text-teal-400" />
                  {reservedUnit.status === 'SOLD' ? 'الوحدة المباعة' : 'الوحدة المحجوزة'}
                </h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-500/20 text-teal-300 border border-teal-500/30">
                  {reservedUnit.status === 'SOLD' ? 'مباعة' : 'محجوزة'}
                </span>
              </div>
              <p className="text-xs font-bold text-slate-100">
                الوحدة {reservedUnit.unit_number} - {reservedUnit.project_name}
              </p>
              <p className="text-[11px] text-slate-400">
                {reservedUnit.location} • {reservedUnit.bedrooms} غرف • {reservedUnit.area} م²
              </p>
              <p className="text-sm font-black text-brand-300 pt-1 border-t border-slate-800">
                {reservedUnit.total_price.toLocaleString()} {reservedUnit.currency}
              </p>
            </div>
          )}

          {/* Smart Recommended Alternative Properties */}
          {!dealClosed && (
            <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-sm text-white flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-amber-400" />
                  وحدات بديلة مطابقة بالمخزون
                </h3>
                <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400">
                  {alternatives.length} متاح
                </span>
              </div>

              <div className="space-y-3">
                {alternatives.length === 0 ? (
                  <p className="text-xs text-slate-500 py-4 text-center">لا توجد وحدات مطابقة حالياً</p>
                ) : (
                  alternatives.map((alt: any) => (
                    <div
                      key={alt.property_id}
                      className="p-3.5 rounded-2xl bg-slate-800/40 border border-slate-800 hover:border-brand-500/40 transition-colors text-xs space-y-2"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-bold text-slate-100">الوحدة {alt.unit_number} - {alt.project_name}</h4>
                          <p className="text-[11px] text-slate-400">{alt.location} • {alt.bedrooms} غرف • {alt.area} م²</p>
                        </div>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                          {alt.match_score}% تطابق
                        </span>
                      </div>

                      <div className="flex justify-between items-center text-[11px] pt-1 border-t border-slate-800">
                        <span className="font-black text-brand-300">
                          {alt.total_price.toLocaleString()} {alt.currency}
                        </span>
                        <span className="text-slate-400">{alt.installment_plan}</span>
                      </div>

                      {alt.reasons?.length > 0 && (
                        <p className="text-[10px] text-emerald-400 flex items-center gap-1">
                          <Check className="w-3 h-3" />
                          {alt.reasons[0]}
                        </p>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Unified Tabs (Timeline, Offers, Activities) */}
        <div className="lg:col-span-2 p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
          
          {/* Tabs Navigation Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-800 gap-3">
            <div className="flex items-center gap-1.5 p-1 bg-slate-800/60 rounded-2xl border border-slate-700/60 text-xs">
              <button
                type="button"
                onClick={() => setActiveTab('TIMELINE')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold transition-all ${
                  activeTab === 'TIMELINE'
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <History className="w-3.5 h-3.5" />
                <span>السجل الشامل (Timeline)</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-900/60 text-slate-300">
                  {timeline.length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('OFFERS')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold transition-all ${
                  activeTab === 'OFFERS'
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <MessageCircle className="w-3.5 h-3.5" />
                <span>عروض الواتساب (Offers)</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-900/60 text-slate-300">
                  {propertyOffers.length}
                </span>
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('ACTIVITIES')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold transition-all ${
                  activeTab === 'ACTIVITIES'
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <PhoneCall className="w-3.5 h-3.5" />
                <span>الأنشطة (Activities)</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-900/60 text-slate-300">
                  {activities.length}
                </span>
              </button>
            </div>

            <div className="flex items-center gap-2">
              {activeTab === 'OFFERS' && (
                <button
                  onClick={() => setShareOfferModalOpen(true)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white transition-all shadow-sm"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>إرسال عرض جديد</span>
                </button>
              )}
              {activeTab === 'ACTIVITIES' && (
                <button
                  onClick={() => setActivityModalOpen(true)}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-brand-300 border border-slate-700 transition-all"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>إضافة نشاط</span>
                </button>
              )}
            </div>
          </div>

          {/* Tab 1: Unified Timeline */}
          {activeTab === 'TIMELINE' && (
            <div className="relative ps-6 space-y-6 before:absolute before:top-2 before:bottom-2 before:start-2.5 before:w-0.5 before:bg-slate-800">
              {loadingTimeline ? (
                <div className="py-10 text-center text-xs text-slate-400 animate-pulse">
                  جاري تحميل السجل الزمني الموحد...
                </div>
              ) : timeline.length === 0 ? (
                <p className="text-xs text-slate-500 py-10 text-center">لا توجد أحداث مسجلة في السجل الزمني لهذا العميل.</p>
              ) : (
                timeline.map((item) => {
                  let badgeBg = 'bg-slate-700 text-slate-300';
                  if (item.type === 'PROPERTY_OFFER') {
                    badgeBg = 'bg-emerald-600 text-white';
                  } else if (item.type === 'APPOINTMENT') {
                    badgeBg = 'bg-purple-600 text-white';
                  } else if (item.type === 'FOLLOWUP') {
                    badgeBg = 'bg-amber-600 text-white';
                  } else if (item.type === 'ASSIGNMENT') {
                    badgeBg = 'bg-cyan-600 text-white';
                  } else if (item.subtype === 'CALL') {
                    badgeBg = 'bg-blue-600 text-white';
                  } else if (item.subtype === 'VISIT') {
                    badgeBg = 'bg-purple-600 text-white';
                  }

                  return (
                    <div key={item.id} className="relative group">
                      <div className={`absolute -start-6 top-1 w-5 h-5 rounded-full border-2 border-slate-900 flex items-center justify-center text-[10px] ${badgeBg}`}>
                        •
                      </div>

                      <div className="p-4 rounded-2xl bg-slate-800/40 border border-slate-800 hover:border-slate-700 transition-colors space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">{item.title}</span>
                            {item.status && (
                              <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 font-semibold">
                                {item.status}
                              </span>
                            )}
                            {item.user_name && (
                              <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800/80 text-slate-400">
                                بواسطة {item.user_name}
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-slate-400">
                            {new Date(item.timestamp).toLocaleString('ar-EG')}
                          </span>
                        </div>

                        {item.description && (
                          <p className="text-xs text-slate-200 leading-relaxed whitespace-pre-line">{item.description}</p>
                        )}

                        {item.type === 'PROPERTY_OFFER' && item.metadata?.feedback && (
                          <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-[11px] flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                            <span>رد العميل: <strong>{item.metadata.feedback}</strong></span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Tab 2: WhatsApp Property Offers */}
          {activeTab === 'OFFERS' && (
            <div className="space-y-4">
              {propertyOffers.length === 0 ? (
                <div className="py-12 text-center text-xs text-slate-400 bg-slate-800/20 rounded-2xl border border-slate-800 space-y-3">
                  <p>لم يتم إرسال أي عروض عقارية لهذا العميل حتى الآن.</p>
                  <button
                    onClick={() => setShareOfferModalOpen(true)}
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white inline-flex items-center gap-1.5"
                  >
                    <MessageCircle className="w-3.5 h-3.5" />
                    <span>مشاركة أول وحدة الآن</span>
                  </button>
                </div>
              ) : (
                propertyOffers.map((offer) => {
                  const statusColors: Record<string, string> = {
                    PREPARED: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
                    SHARED: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
                    ACCEPTED: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
                    REJECTED: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
                  };

                  return (
                    <div
                      key={offer.id}
                      className="p-4 rounded-2xl bg-slate-800/40 border border-slate-800 hover:border-slate-700 transition-colors space-y-3"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-sm text-white">
                              الوحدة {offer.property_unit} - {offer.project_name || 'مشروع مستقل'}
                            </span>
                            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${statusColors[offer.status] || 'bg-slate-800 text-slate-300'}`}>
                              {offer.status}
                            </span>
                          </div>
                          <span className="text-[11px] text-slate-400">
                            {offer.property_location} • السعر المعروض: <strong className="text-emerald-400">{offer.custom_price?.toLocaleString()} ج.م</strong>
                          </span>
                        </div>

                        <div className="text-end text-[10px] text-slate-400">
                          <span>بواسطة {offer.created_by_name}</span>
                          <span className="block mt-0.5">{new Date(offer.created_at).toLocaleDateString('ar-EG')}</span>
                        </div>
                      </div>

                      {offer.message_text && (
                        <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800/80 text-xs text-slate-300 leading-relaxed font-sans">
                          <p className="text-[10px] text-slate-400 font-bold mb-1">نص الرسالة المرسلة:</p>
                          {offer.message_text}
                        </div>
                      )}

                      {offer.customer_feedback ? (
                        <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700 text-xs text-slate-200 flex items-center justify-between">
                          <div>
                            <span className="text-[10px] text-slate-400 block">رد فعل العميل المسجل:</span>
                            <strong className="text-brand-300">{offer.customer_feedback}</strong>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedOfferForFeedback(offer);
                              setFeedbackText(offer.customer_feedback || '');
                              setFeedbackStatus(offer.status);
                              setFeedbackModalOpen(true);
                            }}
                            className="text-[10px] text-slate-400 hover:text-white underline"
                          >
                            تعديل الرد
                          </button>
                        </div>
                      ) : (
                        <div className="flex justify-end pt-1">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedOfferForFeedback(offer);
                              setFeedbackText('');
                              setFeedbackStatus('ACCEPTED');
                              setFeedbackModalOpen(true);
                            }}
                            className="px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-brand-300 border border-brand-500/30 flex items-center gap-1.5"
                          >
                            <MessageSquare className="w-3.5 h-3.5" />
                            <span>تسجيل رد العميل على العرض</span>
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Tab 3: Direct Activities */}
          {activeTab === 'ACTIVITIES' && (
            <div className="relative ps-6 space-y-6 before:absolute before:top-2 before:bottom-2 before:start-2.5 before:w-0.5 before:bg-slate-800">
              {activities.length === 0 ? (
                <p className="text-xs text-slate-500 py-10 text-center">لا توجد أنشطة مسجلة لهذا العميل حتى الآن.</p>
              ) : (
                activities.map((act: any) => (
                  <div key={act.id} className="relative group">
                    <div className={`absolute -start-6 top-1 w-5 h-5 rounded-full border-2 border-slate-900 flex items-center justify-center text-[10px] ${
                      act.activity_type === 'VISIT'
                        ? 'bg-purple-600 text-white'
                        : act.activity_type === 'CALL'
                          ? 'bg-brand-600 text-white'
                          : 'bg-slate-700 text-slate-300'
                    }`}>
                      •
                    </div>

                    <div className="p-4 rounded-2xl bg-slate-800/40 border border-slate-800 hover:border-slate-700 transition-colors space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white">{act.activity_type}</span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                            بواسطة {act.user_name}
                          </span>
                        </div>
                        <span className="text-[10px] text-slate-400">
                          {new Date(act.created_at).toLocaleString('ar-EG')}
                        </span>
                      </div>

                      <p className="text-xs text-slate-200 leading-relaxed">{act.summary}</p>

                      {act.objection && (
                        <div className="p-2 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px] flex items-center gap-1.5">
                          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                          <span>اعتراض مسجل: <strong>{act.objection}</strong></span>
                        </div>
                      )}

                      {act.next_action && (
                        <div className="text-[11px] text-brand-300 font-medium">
                          الإجراء التالي: {act.next_action}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

        </div>
      </div>

      {pendingStage && (
        <UnitPickerModal
          isOpen
          leadId={lead.id}
          leadName={lead.full_name}
          targetStage={pendingStage}
          onClose={() => setPendingStage(null)}
          onConfirm={async (propertyId) => {
            await sendStage(pendingStage, propertyId);
            setPendingStage(null);
          }}
        />
      )}

      {/* Add Activity Modal */}
      {activityModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl relative text-start">
            <h3 className="font-bold text-base text-white mb-3">تسجيل نشاط جديد للعميل</h3>
            <form onSubmit={handleAddActivity} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 mb-1 font-semibold">نوع النشاط</label>
                <select
                  value={activityType}
                  onChange={(e) => setActivityType(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                >
                  <option value="CALL">مكالمة هاتفية (Call)</option>
                  <option value="WHATSAPP">محادثة واتساب (WhatsApp)</option>
                  <option value="MEETING">اجتماع بمقر الشركة (Office Meeting)</option>
                  <option value="VISIT">معاينة موقع (Site Visit)</option>
                  <option value="NOTE">ملاحظة داخلية (Internal Note)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">ملخص ما دار في النشاط *</label>
                <textarea
                  required
                  rows={3}
                  value={activitySummary}
                  onChange={(e) => setActivitySummary(e.target.value)}
                  placeholder="مثال: تم الاتصال بالعميل وأكد اهتمامه بوحدات التجمع..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">نتيجة المكالمة / الخطوة التالية</label>
                <input
                  type="text"
                  value={activityOutcome}
                  onChange={(e) => setActivityOutcome(e.target.value)}
                  placeholder="مثال: مهتم وطلب إرسال البروشور"
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                />
              </div>

              <div className="pt-3 flex justify-end gap-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setActivityModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white"
                >
                  حفظ النشاط
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Transfer Request Modal */}
      {transferModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl relative text-start">
            <h3 className="font-bold text-base text-white mb-1">طلب نقل وتحويل العميل (Lead Transfer)</h3>
            <p className="text-xs text-slate-400 mb-4">
              إرسال طلب رسمي لإعادة إسناد العميل لمستشار عقاري آخر مع الاحتفاظ بكافة السجلات
            </p>

            <form onSubmit={handleRequestTransfer} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 mb-1 font-semibold">المستشار المطلوب نقله إليه *</label>
                <select
                  required
                  value={transferAgentId}
                  onChange={(e) => setTransferAgentId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                >
                  <option value="">-- اختر المستشار العقاري --</option>
                  {companyUsers
                    .filter((u) => u.id !== lead.assigned_agent_id)
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name} ({u.role})
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">سبب النقل *</label>
                <select
                  value={transferReason}
                  onChange={(e) => setTransferReason(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                >
                  <option value="Project Specialization">تخصص المستشار في المشروع (Project Specialization)</option>
                  <option value="Location Preference">اختلاف المنطقة الجغرافية (Location Preference)</option>
                  <option value="Agent Unavailable">عدم تفرغ أو إجازة المستشار الحالي (Agent Unavailable)</option>
                  <option value="Workload Balancing">توزيع أحمال العمل بالفريق (Workload Balancing)</option>
                  <option value="Customer Request">بناءً على رغبة العميل (Customer Request)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">ملاحظات إضافية للمدير</label>
                <textarea
                  rows={2}
                  value={transferNotes}
                  onChange={(e) => setTransferNotes(e.target.value)}
                  placeholder="أسباب التوصية بالنقل..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                />
              </div>

              <div className="pt-3 flex justify-end gap-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setTransferModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={!transferAgentId}
                  className="px-5 py-2 rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white"
                >
                  إرسال طلب النقل
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Send Property via WhatsApp Modal */}
      <SendPropertyOfferModal
        isOpen={shareOfferModalOpen}
        onClose={() => setShareOfferModalOpen(false)}
        leadId={lead.id}
        leadName={lead.full_name}
        leadPhone={lead.phone}
        onSuccess={() => {
          fetchLeadDetails();
          loadTimelineAndOffers();
        }}
      />

      {/* Record Offer Feedback Modal */}
      {feedbackModalOpen && selectedOfferForFeedback && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl relative text-start">
            <h3 className="font-bold text-base text-white mb-1">تسجيل رد فعل العميل على العرض</h3>
            <p className="text-xs text-slate-400 mb-4">
              الوحدة {selectedOfferForFeedback.property_unit} - {selectedOfferForFeedback.project_name || 'مشروع مستقل'}
            </p>

            <form onSubmit={handleRecordFeedback} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 mb-1 font-semibold">حالة وموقف العميل من العرض *</label>
                <select
                  value={feedbackStatus}
                  onChange={(e) => setFeedbackStatus(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 font-semibold"
                >
                  <option value="ACCEPTED">مهتم وموافق مبدئياً (ACCEPTED)</option>
                  <option value="REJECTED">غير مهتم أو رفض العرض (REJECTED)</option>
                  <option value="PREPARED">قيد الدراسة والتفكير (UNDER REVIEW)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">تفاصيل رد العميل وملاحظاته *</label>
                <textarea
                  required
                  rows={3}
                  value={feedbackText}
                  onChange={(e) => setFeedbackText(e.target.value)}
                  placeholder="مثال: وافق على الموقع لكن طلب خصم 5% على الكاش..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500"
                />
              </div>

              <div className="pt-3 flex justify-end gap-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => {
                    setFeedbackModalOpen(false);
                    setSelectedOfferForFeedback(null);
                  }}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={submittingFeedback}
                  className="px-5 py-2 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white"
                >
                  {submittingFeedback ? 'جاري الحفظ...' : 'حفظ الرد'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};