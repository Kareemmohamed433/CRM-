import React, { useEffect, useState } from 'react';
import { 
  Users, Search, Filter, Plus, Phone, Mail, Clock, 
  Sparkles, AlertCircle, ChevronRight, Mic, CheckCircle2 
} from 'lucide-react';
import { api } from '../api/client';
import { Lead, PipelineStage, PriorityLevel } from '../types';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const LeadsPage: React.FC = () => {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState<string>('');
  const [priorityFilter, setPriorityFilter] = useState<string>('');
  const [createModalOpen, setCreateModalOpen] = useState(false);
  
  // New lead form state
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [source, setSource] = useState('Meta Ads');
  const [intentType, setIntentType] = useState('BUY');
  const [preferredLocation, setPreferredLocation] = useState('');
  const [budgetMax, setBudgetMax] = useState('');
  const [propertyType, setPropertyType] = useState('Apartment');
  const [bedrooms, setBedrooms] = useState('');
  const [notes, setNotes] = useState('');
  const [assignedAgentId, setAssignedAgentId] = useState('');
  const [agents, setAgents] = useState<any[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const navigate = useNavigate();
  const { user, t } = useAuth();
  const canAssign = ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER', 'TEAM_LEADER'].includes(user?.role || '');

  const fetchLeads = () => {
    setLoading(true);
    let url = `/leads?search=${encodeURIComponent(search)}`;
    if (stageFilter) url += `&stage=${stageFilter}`;
    if (priorityFilter) url += `&priority=${priorityFilter}`;

    api.get<Lead[]>(url)
      .then(setLeads)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchLeads();
  }, [stageFilter, priorityFilter]);

  useEffect(() => {
    if (canAssign) {
      api.get<any[]>('/agents')
        .then(setAgents)
        .catch(() => {});
    }
  }, [canAssign]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchLeads();
  };

  const handleCreateLead = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    if (!fullName.trim()) {
      setFormError('يرجى إدخال اسم العميل بالكامل');
      return;
    }

    const digitsOnly = phone.replace(/[^0-9]/g, '');
    if (digitsOnly.length < 10) {
      setFormError('يرجى إدخال رقم هاتف صحيح (10 أرقام على الأقل)');
      return;
    }

    setSubmitting(true);

    try {
      const payload: any = {
        full_name: fullName.trim(),
        phone: phone.trim(),
        email: email.trim() || undefined,
        source: source || 'Meta Ads',
        tags: intentType || 'BUY',
        property_type: propertyType || 'Apartment',
        purchase_timeline: 'Immediate (1 month)',
      };

      if (preferredLocation.trim()) {
        payload.preferred_location = preferredLocation.trim();
      }
      if (budgetMax.trim()) {
        const b = parseFloat(budgetMax);
        if (!isNaN(b) && b > 0) payload.budget_max = b;
      }
      if (bedrooms.trim()) {
        const r = parseInt(bedrooms);
        if (!isNaN(r) && r > 0) payload.bedrooms = r;
      }
      if (notes.trim()) {
        payload.notes = notes.trim();
      }
      if (assignedAgentId && canAssign) {
        payload.assigned_agent_id = parseInt(assignedAgentId);
      }

      await api.post('/leads', payload);

      setCreateModalOpen(false);
      // Reset form
      setFullName('');
      setPhone('');
      setEmail('');
      setSource('Meta Ads');
      setIntentType('BUY');
      setPreferredLocation('');
      setBudgetMax('');
      setPropertyType('Apartment');
      setBedrooms('');
      setNotes('');
      setAssignedAgentId('');
      fetchLeads();
    } catch (err: any) {
      setFormError(err.message || 'فشل إضافة العميل');
    } finally {
      setSubmitting(false);
    }
  };

  const getStageBadgeColor = (stage: PipelineStage) => {
    switch (stage) {
      case 'NEW': return 'bg-sky-500/10 text-sky-400 border-sky-500/20';
      case 'QUALIFIED': return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
      case 'VISIT_SCHEDULED': return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'VISIT_COMPLETED': return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      case 'NEGOTIATION': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      case 'WON': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'LOST': return 'bg-slate-700/50 text-slate-400 border-slate-600/30';
      default: return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  const getPriorityBadgeColor = (prio: PriorityLevel) => {
    switch (prio) {
      case 'URGENT': return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
      case 'HIGH': return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      case 'MEDIUM': return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      default: return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  return (
    <div className="space-y-6 text-start">
      {/* Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white flex items-center gap-2">
            <Users className="w-6 h-6 text-brand-400" />
            <span>إدارة العملاء والطلبات (Leads & Customers)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            متابعة دورة حياة العميل، وتسجيل الاهتمامات، ونقاط الأولوية الذكية
          </p>
        </div>

        <button
          onClick={() => {
            setFormError('');
            setCreateModalOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-lg shadow-brand-600/20 shrink-0"
        >
          <Plus className="w-4 h-4" />
          <span>إضافة عميل جديد (Add Client)</span>
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 shadow-lg flex flex-col md:flex-row gap-3 items-center justify-between">
        <form onSubmit={handleSearchSubmit} className="relative w-full md:w-96">
          <Search className="w-4 h-4 text-slate-400 absolute top-3 start-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="بحث بالاسم، رقم الهاتف، أو البريد..."
            className="w-full bg-slate-800/80 border border-slate-700/80 rounded-xl py-2 ps-9 pe-4 text-xs sm:text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
          />
        </form>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          {/* Stage filter */}
          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-xs rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
          >
            <option value="">جميع المراحل (All Stages)</option>
            <option value="NEW">عميل جديد (NEW)</option>
            <option value="CONTACTED">تم التواصل (CONTACTED)</option>
            <option value="QUALIFIED">مؤهل (QUALIFIED)</option>
            <option value="VISIT_SCHEDULED">معاينة مجدولة (VISIT_SCHEDULED)</option>
            <option value="VISIT_COMPLETED">تمت المعاينة (VISIT_COMPLETED)</option>
            <option value="NEGOTIATION">تفاوض (NEGOTIATION)</option>
            <option value="WON">صفقة ناجحة (WON)</option>
            <option value="LOST">صفقة خاسرة (LOST)</option>
          </select>

          {/* Priority filter */}
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-xs rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
          >
            <option value="">جميع الأولويات</option>
            <option value="URGENT">عاجل (URGENT)</option>
            <option value="HIGH">مرتفع (HIGH)</option>
            <option value="MEDIUM">متوسط (MEDIUM)</option>
            <option value="LOW">منخفض (LOW)</option>
          </select>
        </div>
      </div>

      {/* Leads Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl shadow-xl overflow-hidden">
        {loading ? (
          <div className="py-20 text-center text-slate-400 text-xs animate-pulse">
            جاري تحميل قائمة العملاء...
          </div>
        ) : leads.length === 0 ? (
          <div className="py-20 text-center text-slate-400 text-xs">
            لا يوجد عملاء مطابقين لخيارات البحث المحددة.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-start">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-900/60">
                  <th className="py-3.5 px-4 font-semibold">اسم العميل</th>
                  <th className="py-3.5 px-4 font-semibold">المرحلة الحالية</th>
                  <th className="py-3.5 px-4 font-semibold">الميزانية والموقع</th>
                  <th className="py-3.5 px-4 font-semibold text-center">درجة الجاهزية (Score)</th>
                  <th className="py-3.5 px-4 font-semibold">الأولوية</th>
                  <th className="py-3.5 px-4 font-semibold">المستشار المسؤول</th>
                  <th className="py-3.5 px-4 font-semibold">المتابعة القادمة</th>
                  <th className="py-3.5 px-4"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {leads.map((l) => (
                  <tr
                    key={l.id}
                    onClick={() => navigate(`/leads/${l.id}`)}
                    className="hover:bg-slate-800/40 transition-colors cursor-pointer group"
                  >
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-white group-hover:text-brand-400 transition-colors">
                        {l.full_name}
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                        <span className="flex items-center gap-1"><Phone className="w-3 h-3" />{l.phone}</span>
                        {l.email && <span className="flex items-center gap-1"><Mail className="w-3 h-3" />{l.email}</span>}
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <span className={`inline-block px-2.5 py-1 rounded-full text-[10px] font-bold border ${getStageBadgeColor(l.pipeline_stage)}`}>
                        {l.pipeline_stage.replace('_', ' ')}
                      </span>
                    </td>

                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-200">
                        {l.budget_max > 0 ? `${l.budget_max.toLocaleString()} ج.م` : 'غير محدد'}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {l.preferred_location || l.property_type || 'شقة سكني'}
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-center">
                      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700">
                        <Sparkles className="w-3 h-3 text-amber-400" />
                        <span className="font-black text-amber-300">{l.score}</span>
                        <span className="text-[10px] text-slate-400">/ 100</span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <span className={`inline-block px-2 py-0.5 rounded-md text-[10px] font-semibold border ${getPriorityBadgeColor(l.priority)}`}>
                        {l.priority}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-slate-300 font-medium">
                      {l.assigned_agent_name || 'غير مسند'}
                    </td>

                    <td className="py-3.5 px-4">
                      {l.next_followup_date ? (
                        <span className="text-slate-300 flex items-center gap-1">
                          <Clock className="w-3 h-3 text-brand-400" />
                          {new Date(l.next_followup_date).toLocaleDateString('ar-EG')}
                        </span>
                      ) : (
                        <span className="text-rose-400 text-[11px] flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" />
                          بدون خطوة محددة
                        </span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 text-end">
                      <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-white transition-colors" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create Lead Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-xl w-full p-6 shadow-2xl relative text-start my-8">
            <h3 className="font-bold text-base text-white mb-1">إضافة عميل جديد للنظام (New Client)</h3>
            <p className="text-xs text-slate-400 mb-4">أدخل بيانات العميل ومتطلبات العقار المفضل بدقة لضمان تسجيله في السي آر إم</p>

            {formError && (
              <div className="mb-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateLead} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">اسم العميل بالكامل *</label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="مثال: أحمد عبد الله"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">رقم الهاتف *</label>
                  <input
                    type="tel"
                    required
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="010XXXXXXXX"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">البريد الإلكتروني</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@example.com"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">نوع الطلب</label>
                  <select
                    value={intentType}
                    onChange={(e) => setIntentType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  >
                    <option value="BUY">شراء (BUY)</option>
                    <option value="RENT">إيجار (RENT)</option>
                    <option value="SELL">بيع (SELL)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">مصدر العميل</label>
                  <select
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  >
                    <option value="Meta Ads">إعلانات فيسبوك / إنستغرام</option>
                    <option value="Google Ads">إعلانات جوجل</option>
                    <option value="Referral">ترشيح عميل (Referral)</option>
                    <option value="Direct Call">اتصال مباشر</option>
                    <option value="Walk-in">زيارة للمعرض</option>
                    <option value="Website">الموقع الإلكتروني</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">الميزانية المتوقعة (ج.م)</label>
                  <input
                    type="number"
                    value={budgetMax}
                    onChange={(e) => setBudgetMax(e.target.value)}
                    placeholder="مثال: 5000000"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">المنطقة المفضلة</label>
                  <input
                    type="text"
                    value={preferredLocation}
                    onChange={(e) => setPreferredLocation(e.target.value)}
                    placeholder="التجمع الخامس، زايد..."
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">نوع العقار</label>
                  <select
                    value={propertyType}
                    onChange={(e) => setPropertyType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  >
                    <option value="Apartment">شقة (Apartment)</option>
                    <option value="Villa">فيلا مستقلة (Villa)</option>
                    <option value="Townhouse">تاون هاوس (Townhouse)</option>
                    <option value="Duplex">دوبلكس (Duplex)</option>
                    <option value="Penthouse">بنتهاوس (Penthouse)</option>
                    <option value="Chalet">شاليه (Chalet)</option>
                    <option value="Commercial">تجاري / إداري (Commercial)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">عدد الغرف</label>
                  <input
                    type="number"
                    value={bedrooms}
                    onChange={(e) => setBedrooms(e.target.value)}
                    placeholder="مثال: 3"
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                  />
                </div>

                {canAssign && (
                  <div>
                    <label className="block text-slate-300 mb-1 font-semibold">تعيين لمستشار عقاري</label>
                    <select
                      value={assignedAgentId}
                      onChange={(e) => setAssignedAgentId(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                    >
                      <option value="">تلقائي (حسب دورك أو غير معين)</option>
                      {agents.map((ag) => (
                        <option key={ag.id} value={ag.id}>
                          {ag.full_name} ({ag.role})
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">ملاحظات واهتمامات العميل</label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="أي تفاصيل خاصة برغبة العميل وطريقة السداد المفضلة..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40 resize-none"
                />
              </div>

              <div className="pt-3 flex justify-end gap-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-6 py-2.5 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-md flex items-center gap-2 disabled:opacity-50"
                >
                  {submitting ? 'جاري الحفظ...' : 'حفظ وتسجيل العميل'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
