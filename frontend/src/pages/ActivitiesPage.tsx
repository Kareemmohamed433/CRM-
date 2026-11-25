import React, { useEffect, useState } from 'react';
import { 
  PhoneCall, Plus, Search, Filter, AlertCircle, Sparkles, 
  CheckCircle2, Clock, Calendar, Check, ExternalLink 
} from 'lucide-react';
import { api } from '../api/client';
import { Activity, Lead } from '../types';
import { useNavigate } from 'react-router-dom';

export const ActivitiesPage: React.FC = () => {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [visitModalOpen, setVisitModalOpen] = useState(false);

  // Visit outcome state
  const [selectedLeadId, setSelectedLeadId] = useState('');
  const [visitOutcome, setVisitOutcome] = useState('Completed - Price Objection');
  const [visitObjection, setVisitObjection] = useState('Price too high / السعر مرتفع (> 4M)');
  const [statedBudget, setStatedBudget] = useState('3900000');
  const [visitNotes, setVisitNotes] = useState('العميل عاين شقة في التجمع وعجبته لكن السعر أعلى من ميزانيته، محتاج بديل تحت 4 مليون');
  const [nextFollowupDate, setNextFollowupDate] = useState('2026-11-01T14:00');
  const [alternativesResult, setAlternativesResult] = useState<any[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const navigate = useNavigate();

  const fetchData = () => {
    setLoading(true);
    Promise.all([
      api.get<Activity[]>('/activities'),
      api.get<Lead[]>('/leads')
    ])
      .then(([acts, lds]) => {
        setActivities(acts);
        setLeads(lds);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRecordVisitOutcome = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLeadId) return;
    setSubmitting(true);
    try {
      const res = await api.post<any>('/activities/visit-outcome', {
        lead_id: parseInt(selectedLeadId),
        outcome: visitOutcome,
        objection: visitObjection,
        customer_stated_budget: parseFloat(statedBudget) || 0,
        feedback_notes: visitNotes,
        suggest_alternatives: true,
        next_followup_date: nextFollowupDate ? `${nextFollowupDate}:00` : undefined,
      });

      setAlternativesResult(res.recommended_alternatives || []);
      fetchData();
    } catch (err: any) {
      alert(`خطأ: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 text-start">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white flex items-center gap-2">
            <PhoneCall className="w-6 h-6 text-brand-400" />
            <span>سجل الأنشطة والمعاينات والاعتراضات (Activities & Visits)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            توثيق المعاينات، أسباب رفض الوحدات، وتوليد المقترحات البديلة للعملاء
          </p>
        </div>

        <button
          onClick={() => {
            setAlternativesResult([]);
            setVisitModalOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-500 text-white transition-all shadow-lg shadow-purple-600/20 shrink-0"
        >
          <Plus className="w-4 h-4" />
          <span>تسجيل نتيجة معاينة واعتراض</span>
        </button>
      </div>

      {/* Activities Feed */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-20 text-center text-slate-400 text-xs animate-pulse">
            جاري تحميل الأنشطة...
          </div>
        ) : activities.length === 0 ? (
          <div className="py-20 text-center text-slate-400 text-xs bg-slate-900 rounded-3xl border border-slate-800">
            لا توجد أنشطة مسجلة حتى الآن.
          </div>
        ) : (
          activities.map((act) => (
            <div
              key={act.id}
              className="p-4 rounded-2xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all shadow-md flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="flex items-start gap-3.5">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 font-bold text-xs ${
                  act.activity_type === 'VISIT'
                    ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                    : 'bg-brand-500/20 text-brand-400 border border-brand-500/30'
                }`}>
                  {act.activity_type === 'VISIT' ? 'معاينة' : 'مكالمة'}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <span 
                      onClick={() => navigate(`/leads/${act.lead_id}`)}
                      className="font-bold text-sm text-white hover:text-brand-400 cursor-pointer transition-colors"
                    >
                      {act.lead_name || `عميل #${act.lead_id}`}
                    </span>
                    <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded">
                      بواسطة {act.user_name}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 mt-1 max-w-2xl leading-relaxed">{act.summary}</p>

                  {act.objection && (
                    <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px]">
                      <AlertCircle className="w-3 h-3" />
                      الاعتراض: <strong>{act.objection}</strong>
                    </div>
                  )}
                </div>
              </div>

              <div className="text-end shrink-0 text-xs text-slate-400">
                <span>{new Date(act.created_at).toLocaleDateString('ar-EG')}</span>
                {act.next_action && (
                  <p className="text-[11px] text-brand-400 font-medium mt-1 truncate max-w-xs">
                    {act.next_action}
                  </p>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Record Visit Outcome Modal */}
      {visitModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-2xl w-full p-6 shadow-2xl relative text-start max-h-[90vh] overflow-y-auto">
            <h3 className="font-bold text-base text-white mb-1">تسجيل نتيجة المعاينة واعتراض العميل</h3>
            <p className="text-xs text-slate-400 mb-4">
              ملاحظة معمارية هامة: رفض الوحدة المعاينة لا يعني خسارة العميل (Lead is not Lost)! سيتم الاحتفاظ باهتمام العميل والبحث عن وحدات بديلة.
            </p>

            {alternativesResult.length > 0 ? (
              <div className="space-y-4">
                <div className="p-3 bg-emerald-500/20 border border-emerald-500/30 rounded-2xl text-emerald-300 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5" />
                  <span>تم حفظ المعاينة وتحديث ميزانية العميل واقتراح البدائل التالية تلقائياً:</span>
                </div>

                <div className="space-y-2.5">
                  {alternativesResult.map((alt) => (
                    <div key={alt.property_id} className="p-3 rounded-xl bg-slate-800 border border-slate-700 text-xs space-y-1">
                      <div className="flex justify-between font-bold text-white">
                        <span>الوحدة {alt.unit_number} - {alt.project_name}</span>
                        <span className="text-emerald-400">{alt.total_price.toLocaleString()} {alt.currency}</span>
                      </div>
                      <p className="text-slate-400 text-[11px]">{alt.location} • {alt.bedrooms} غرف • {alt.installment_plan}</p>
                      {alt.reasons?.length > 0 && (
                        <p className="text-[10px] text-emerald-300">✓ {alt.reasons[0]}</p>
                      )}
                    </div>
                  ))}
                </div>

                <div className="pt-3 flex justify-end">
                  <button
                    onClick={() => {
                      setVisitModalOpen(false);
                      setAlternativesResult([]);
                    }}
                    className="px-5 py-2 rounded-xl text-xs font-bold bg-brand-600 text-white"
                  >
                    تم ومتابعة العميل
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleRecordVisitOutcome} className="space-y-3.5 text-xs">
                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">اختر العميل *</label>
                  <select
                    required
                    value={selectedLeadId}
                    onChange={(e) => setSelectedLeadId(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                  >
                    <option value="">-- اختر العميل --</option>
                    {leads.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.full_name} ({l.phone}) - {l.pipeline_stage}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-300 mb-1 font-semibold">نتيجة المعاينة</label>
                    <select
                      value={visitOutcome}
                      onChange={(e) => setVisitOutcome(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                    >
                      <option value="Completed - Interested">معاينة ناجحة - مهتم بالشراء</option>
                      <option value="Completed - Price Objection">معاينة منتهية - اعتراض على السعر</option>
                      <option value="Completed - Down Payment Objection">معاينة منتهية - اعتراض على المقدم</option>
                      <option value="Completed - Location Objection">معاينة منتهية - اعتراض على الموقع</option>
                      <option value="No Show">لم يحضر العميل (No Show)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-slate-300 mb-1 font-semibold">نوع وسبب الاعتراض</label>
                    <input
                      type="text"
                      value={visitObjection}
                      onChange={(e) => setVisitObjection(e.target.value)}
                      placeholder="السعر مرتفع، المقدم كبير..."
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-300 mb-1 font-semibold">الميزانية الجديدة المصرح بها من العميل (ج.م)</label>
                    <input
                      type="number"
                      value={statedBudget}
                      onChange={(e) => setStatedBudget(e.target.value)}
                      placeholder="4000000"
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-300 mb-1 font-semibold">موعد المتابعة القادمة لتقديم البدائل</label>
                    <input
                      type="datetime-local"
                      value={nextFollowupDate}
                      onChange={(e) => setNextFollowupDate(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-300 mb-1 font-semibold">ملاحظات المعاينة وتفاصيل قرار العميل *</label>
                  <textarea
                    rows={3}
                    required
                    value={visitNotes}
                    onChange={(e) => setVisitNotes(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                  />
                </div>

                <div className="pt-3 flex justify-end gap-3 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setVisitModalOpen(false)}
                    className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
                  >
                    إلغاء
                  </button>
                  <button
                    type="submit"
                    disabled={submitting || !selectedLeadId}
                    className="flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-bold bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                    <span>{submitting ? 'جاري المعالجة...' : 'تسجيل المعاينة واقتراح البدائل'}</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
