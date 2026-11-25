import React, { useEffect, useState } from 'react';
import {
  Kanban, Plus, Clock, User, Phone, Sparkles, ChevronRight,
  ChevronLeft, AlertCircle, CheckCircle2, DollarSign
} from 'lucide-react';
import { api } from '../api/client';
import { Lead, PipelineStage } from '../types';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { UnitPickerModal } from '../components/modals/UnitPickerModal';

type LeadEx = Lead & {
  reserved_property?: { property_id: number; unit_number: string; total_price: number; currency: string; status: string } | null;
  deal_value?: number | null;
};

// A closed/reserved deal is worth its unit price; otherwise fall back to the lead's budget
const leadValue = (l: LeadEx) => l.deal_value ?? (l.budget_max || 0);

const STAGES: { key: PipelineStage; label: string; color: string }[] = [
  { key: 'NEW', label: 'عميل جديد (New)', color: 'border-t-sky-500' },
  { key: 'CONTACTED', label: 'تم التواصل (Contacted)', color: 'border-t-blue-500' },
  { key: 'QUALIFIED', label: 'مؤهل للشراء (Qualified)', color: 'border-t-indigo-500' },
  { key: 'VISIT_SCHEDULED', label: 'معاينة مجدولة (Visit Set)', color: 'border-t-amber-500' },
  { key: 'VISIT_COMPLETED', label: 'تمت المعاينة (Visited)', color: 'border-t-purple-500' },
  { key: 'NEGOTIATION', label: 'مرحلة التفاوض (Negotiation)', color: 'border-t-orange-500' },
  { key: 'RESERVATION', label: 'حجز مبدئي (Reservation)', color: 'border-t-teal-500' },
  { key: 'WON', label: 'صفقة ناجحة (Won Deal)', color: 'border-t-emerald-500' },
];

export const PipelinePage: React.FC = () => {
  const [leads, setLeads] = useState<LeadEx[]>([]);
  const [pendingMove, setPendingMove] = useState<{ lead: LeadEx; target: 'RESERVATION' | 'WON' } | null>(null);
  const [loading, setLoading] = useState(true);
  const { isRtl } = useAuth();
  const navigate = useNavigate();

  const fetchLeads = () => {
    setLoading(true);
    api.get<LeadEx[]>('/leads')
      .then(setLeads)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchLeads();
  }, []);

  const sendMove = async (leadId: number, targetStage: PipelineStage, propertyId?: number) => {
    await api.patch(`/leads/${leadId}/stage`, {
      pipeline_stage: targetStage,
      property_id: propertyId,
      notes: `نقل مباشر في الـ Kanban إلى ${targetStage}`
    });
    fetchLeads();
  };

  const moveStage = async (lead: LeadEx, targetStage: PipelineStage, e: React.MouseEvent) => {
    e.stopPropagation();
    // Reservation / Won need a unit: ask for it unless the lead already holds one
    if ((targetStage === 'RESERVATION' || targetStage === 'WON') && !lead.reserved_property) {
      setPendingMove({ lead, target: targetStage });
      return;
    }
    try {
      await sendMove(lead.id, targetStage);
    } catch (err: any) {
      alert(`فشل النقل: ${err.message}`);
    }
  };

  const totalPipelineValue = leads
    .filter(l => l.pipeline_stage !== 'LOST')
    .reduce((sum, l) => sum + leadValue(l), 0);

  return (
    <div className="space-y-6 text-start">
      {/* Header & Pipeline Total Value */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white flex items-center gap-2">
            <Kanban className="w-6 h-6 text-brand-400" />
            <span>مراحل البيع التفاعلية (Sales Pipeline Kanban)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            متابعة حركة الصفقات والتقدم المرحلي اللحظي لكل عميل
          </p>
        </div>

        <div className="flex items-center gap-4 bg-slate-800/60 border border-slate-700/60 px-4 py-2 rounded-2xl">
          <div className="text-end">
            <span className="text-[10px] text-slate-400 block">إجمالي قيمة الصفقات الجارية</span>
            <span className="text-base sm:text-lg font-black text-emerald-400">
              {totalPipelineValue.toLocaleString()} ج.م
            </span>
          </div>
        </div>
      </div>

      {/* Kanban Board Container */}
      {loading ? (
        <div className="py-24 text-center text-slate-400 text-xs animate-pulse">
          جاري تجهيز لوحة الـ Kanban...
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-6">
          {STAGES.map((col, colIdx) => {
            const colLeads = leads.filter(l => l.pipeline_stage === col.key);
            const colValue = colLeads.reduce((s, l) => s + leadValue(l), 0);

            return (
              <div
                key={col.key}
                className={`w-72 shrink-0 bg-slate-900/80 border border-slate-800 rounded-2xl border-t-4 ${col.color} flex flex-col max-h-[75vh] shadow-xl`}
              >
                {/* Column Header */}
                <div className="p-3.5 border-b border-slate-800/80 flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-xs text-white">{col.label}</h3>
                    <span className="text-[10px] text-slate-400">
                      {colValue > 0 ? `${(colValue / 1_000_000).toFixed(1)}M ج.م` : '0 ج.م'}
                    </span>
                  </div>
                  <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] font-bold text-slate-300">
                    {colLeads.length}
                  </span>
                </div>

                {/* Column Cards List */}
                <div className="p-2.5 overflow-y-auto space-y-2.5 flex-1">
                  {colLeads.length === 0 ? (
                    <div className="py-8 text-center text-slate-600 text-[11px]">لا يوجد عملاء</div>
                  ) : (
                    colLeads.map((lead) => (
                      <div
                        key={lead.id}
                        onClick={() => navigate(`/leads/${lead.id}`)}
                        className="p-3 rounded-xl bg-slate-800/50 border border-slate-800 hover:border-brand-500/50 hover:bg-slate-800/80 transition-all cursor-pointer shadow-sm group space-y-2 text-start"
                      >
                        <div className="flex items-start justify-between">
                          <h4 className="font-bold text-xs text-slate-100 group-hover:text-brand-300 transition-colors">
                            {lead.full_name}
                          </h4>
                          <span className="text-[10px] font-black text-amber-400 flex items-center gap-1">
                            <Sparkles className="w-2.5 h-2.5" />
                            {lead.score}
                          </span>
                        </div>

                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-bold text-slate-200">
                            {lead.deal_value
                              ? `${lead.deal_value.toLocaleString()} ج.م`
                              : (lead.budget_max || 0) > 0 ? `${lead.budget_max.toLocaleString()} ج.م` : 'طلب مفتوح'}
                          </span>
                          <span className="text-slate-400 truncate max-w-[100px]">
                            {lead.preferred_location || 'التجمع'}
                          </span>
                        </div>

                        {lead.reserved_property && (
                          <div className="text-[10px] px-2 py-1 rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-300">
                            الوحدة: {lead.reserved_property.unit_number} ({lead.reserved_property.status === 'SOLD' ? 'مباعة' : 'محجوزة'})
                          </div>
                        )}

                        <div className="flex items-center justify-between text-[10px] pt-1.5 border-t border-slate-800 text-slate-400">
                          <span>{lead.assigned_agent_name || 'غير مسند'}</span>
                          {lead.next_followup_date ? (
                            <span className="text-emerald-400 flex items-center gap-1">
                              <Clock className="w-2.5 h-2.5" />
                              {new Date(lead.next_followup_date).toLocaleDateString('ar-EG')}
                            </span>
                          ) : (
                            <span className="text-rose-400">بدون متابعة</span>
                          )}
                        </div>

                        {/* Quick Stage Move Buttons */}
                        <div className="flex items-center justify-between pt-1 gap-1">
                          {colIdx > 0 && (
                            <button
                              onClick={(e) => moveStage(lead, STAGES[colIdx - 1].key, e)}
                              className="p-1 rounded bg-slate-900 hover:bg-slate-700 text-slate-400 hover:text-white"
                              title="رجوع للمرحلة السابقة"
                            >
                              {isRtl ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
                            </button>
                          )}
                          <div className="flex-1"></div>
                          {colIdx < STAGES.length - 1 && (
                            <button
                              onClick={(e) => moveStage(lead, STAGES[colIdx + 1].key, e)}
                              className="px-2 py-1 rounded bg-brand-600/30 hover:bg-brand-600 text-brand-300 hover:text-white text-[10px] font-bold flex items-center gap-0.5 transition-colors"
                              title="تقديم للمرحلة التالية"
                            >
                              <span>تقديم</span>
                              {isRtl ? <ChevronLeft className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                            </button>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {pendingMove && (
        <UnitPickerModal
          isOpen
          leadId={pendingMove.lead.id}
          leadName={pendingMove.lead.full_name}
          targetStage={pendingMove.target}
          onClose={() => setPendingMove(null)}
          onConfirm={async (propertyId) => {
            await sendMove(pendingMove.lead.id, pendingMove.target, propertyId);
            setPendingMove(null);
          }}
        />
      )}
    </div>
  );
};