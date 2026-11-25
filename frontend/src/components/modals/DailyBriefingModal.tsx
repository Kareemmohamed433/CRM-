import React, { useEffect, useState } from 'react';
import { Sparkles, Calendar, Clock, AlertCircle, CheckCircle, ArrowRight, X, PhoneCall } from 'lucide-react';
import { api } from '../../api/client';
import { DailyBriefingData } from '../../types';
import { useNavigate } from 'react-router-dom';

interface DailyBriefingModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DailyBriefingModal: React.FC<DailyBriefingModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [briefing, setBriefing] = useState<DailyBriefingData | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      api.get<DailyBriefingData>('/ai/briefing')
        .then(setBriefing)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-2xl w-full p-6 shadow-2xl relative text-start overflow-hidden max-h-[90vh] flex flex-col">
        {/* Glow */}
        <div className="absolute top-0 start-0 w-64 h-64 bg-amber-500/10 rounded-full blur-3xl pointer-events-none"></div>

        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-amber-500/20 text-amber-400 flex items-center justify-center shadow-inner">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">الموجز اليومي للمبيعات (AI Work Briefing)</h3>
              <p className="text-xs text-slate-400">{briefing?.date_formatted || 'اليوم'}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {loading ? (
            <div className="py-16 text-center text-slate-400 text-sm animate-pulse">
              جاري حساب واستخراج بيانات اليوم وسجلات المتابعات...
            </div>
          ) : briefing ? (
            <>
              {/* Greeting & Summary */}
              <div className="p-4 rounded-2xl bg-gradient-to-r from-amber-500/10 via-slate-800/60 to-slate-800/40 border border-amber-500/20">
                <h4 className="text-sm font-bold text-amber-300 mb-1">{briefing.greeting}</h4>
                <p className="text-xs text-slate-200 leading-relaxed">{briefing.summary_text}</p>
              </div>

              {/* Metric Quick Stats */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                <div className="bg-slate-800/60 border border-slate-800 p-3 rounded-xl text-center">
                  <span className="text-[11px] text-slate-400 block mb-1">متابعات اليوم</span>
                  <span className="text-xl font-black text-brand-400">{briefing.metrics.due_today}</span>
                </div>
                <div className={`p-3 rounded-xl text-center border ${
                  briefing.metrics.overdue > 0
                    ? 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                    : 'bg-slate-800/60 border-slate-800 text-slate-300'
                }`}>
                  <span className="text-[11px] text-slate-400 block mb-1">متأخرة</span>
                  <span className="text-xl font-black">{briefing.metrics.overdue}</span>
                </div>
                <div className="bg-slate-800/60 border border-slate-800 p-3 rounded-xl text-center">
                  <span className="text-[11px] text-slate-400 block mb-1">معاينات اليوم</span>
                  <span className="text-xl font-black text-emerald-400">{briefing.metrics.today_visits}</span>
                </div>
                <div className="bg-slate-800/60 border border-slate-800 p-3 rounded-xl text-center">
                  <span className="text-[11px] text-slate-400 block mb-1">بدون متابعة</span>
                  <span className="text-xl font-black text-amber-400">{briefing.metrics.stalled_leads}</span>
                </div>
              </div>

              {/* Overdue Items (High Priority Alert) */}
              {briefing.overdue_followups.length > 0 && (
                <div className="space-y-2">
                  <h5 className="text-xs font-bold text-rose-400 flex items-center gap-1.5">
                    <AlertCircle className="w-4 h-4" />
                    متابعات متأخرة تتطلب الاتصال الفوري:
                  </h5>
                  <div className="space-y-1.5">
                    {briefing.overdue_followups.map((f) => (
                      <div
                        key={f.id}
                        className="flex items-center justify-between p-3 rounded-xl bg-rose-500/5 border border-rose-500/20 text-xs hover:border-rose-500/40 transition-colors"
                      >
                        <div>
                          <p className="font-semibold text-white">{f.lead_name}</p>
                          <p className="text-slate-400 text-[11px] mt-0.5">{f.purpose}</p>
                        </div>
                        <button
                          onClick={() => {
                            onClose();
                            navigate(`/leads/${f.lead_id}`);
                          }}
                          className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold text-[11px] flex items-center gap-1 transition-all"
                        >
                          <PhoneCall className="w-3 h-3" />
                          <span>فتح وسجل الآن</span>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Today's Visits */}
              {briefing.today_visits.length > 0 && (
                <div className="space-y-2">
                  <h5 className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                    <Calendar className="w-4 h-4" />
                    المعاينات والمواعيد المجدولة اليوم:
                  </h5>
                  <div className="space-y-1.5">
                    {briefing.today_visits.map((v) => (
                      <div
                        key={v.id}
                        className="flex items-center justify-between p-3 rounded-xl bg-slate-800/40 border border-slate-800 text-xs"
                      >
                        <div>
                          <p className="font-semibold text-slate-100">{v.lead_name} - {v.title}</p>
                          <p className="text-slate-400 text-[11px] mt-0.5">{v.location}</p>
                        </div>
                        <span className="px-2.5 py-1 rounded-lg bg-emerald-500/20 text-emerald-300 font-bold text-[11px]">
                          {v.time}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              <div className="p-3.5 rounded-2xl bg-slate-800/40 border border-slate-800 space-y-1.5">
                <span className="text-[11px] font-bold text-brand-300 block mb-1">
                  توصيات ذكية لتحسين الإنتاجية اليومية:
                </span>
                {briefing.recommendations.map((rec, idx) => (
                  <p key={idx} className="text-xs text-slate-300 flex items-start gap-2">
                    <span className="text-brand-400 mt-0.5">•</span>
                    <span>{rec}</span>
                  </p>
                ))}
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-slate-800 flex justify-end shrink-0">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-200 hover:bg-slate-700 transition-colors"
          >
            إغلاق
          </button>
        </div>
      </div>
    </div>
  );
};
