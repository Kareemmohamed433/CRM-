import React, { useEffect, useState } from 'react';
import {
  CheckSquare, Plus, Clock, AlertCircle, CheckCircle2,
  Phone, Calendar, User, ArrowRight, RefreshCw, MessageSquare
} from 'lucide-react';
import { api } from '../api/client';
import { FollowUp, Appointment } from '../types';
import { useNavigate } from 'react-router-dom';

interface FollowupsPageProps {
  myTasksOnly?: boolean;
}

export const FollowupsPage: React.FC<FollowupsPageProps> = ({ myTasksOnly = false }) => {
  const [followups, setFollowups] = useState<FollowUp[]>([]);
  const [todayAppointments, setTodayAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'all' | 'due_today' | 'overdue' | 'completed'>('all');
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [selectedFollowup, setSelectedFollowup] = useState<FollowUp | null>(null);

  // Complete modal state
  const [completionOutcome, setCompletionOutcome] = useState('تم التواصل والمتابعة بنجاح');
  const [completionNotes, setCompletionNotes] = useState('');
  const [scheduleNext, setScheduleNext] = useState(false);
  const [nextPurpose, setNextPurpose] = useState('متابعة تجهيز العقد أو زيارة الموقع');
  const [nextDueDate, setNextDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const navigate = useNavigate();

  const fetchFollowups = () => {
    setLoading(true);
    const endpoint = myTasksOnly 
      ? `/followups?filter_type=${tab}&assigned_to_me=true`
      : `/followups?filter_type=${tab}`;
    api.get<FollowUp[]>(endpoint)
      .then(setFollowups)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  // Appointments live in their own table (Calendar page); show today's ones here too
  const fetchTodayAppointments = () => {
    const d = new Date();
    const pad = (n: number) => String(n).padStart(2, '0');
    const day = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    api.get<Appointment[]>(`/appointments?start_date=${day}T00:00:00&end_date=${day}T23:59:59`)
      .then((apps) => setTodayAppointments(apps.filter((a) => a.status === 'SCHEDULED')))
      .catch(() => setTodayAppointments([]));
  };

  useEffect(() => {
    fetchFollowups();
  }, [tab]);

  useEffect(() => {
    fetchTodayAppointments();
  }, []);

  const showAppointments = (tab === 'all' || tab === 'due_today') && todayAppointments.length > 0;

  const handleCompleteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFollowup) return;
    setSubmitting(true);
    try {
      await api.post(`/followups/${selectedFollowup.id}/complete`, {
        completion_outcome: completionOutcome,
        notes: completionNotes,
        schedule_next: scheduleNext,
        next_purpose: scheduleNext ? nextPurpose : undefined,
        next_due_date: scheduleNext && nextDueDate ? `${nextDueDate}:00` : undefined,
      });

      setCompleteModalOpen(false);
      setSelectedFollowup(null);
      fetchFollowups();
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
            <CheckSquare className="w-6 h-6 text-brand-400" />
            <span>مركز المتابعات والمهام (Follow-ups & Tasks)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            إدارة المواعيد المحددة، كشف المتابعات المتأخرة، وتفادي ضياع العملاء
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 space-x-2 space-x-reverse text-xs font-bold">
        <button
          onClick={() => setTab('all')}
          className={`pb-3 px-4 border-b-2 transition-all ${tab === 'all'
            ? 'border-brand-500 text-brand-400'
            : 'border-transparent text-slate-400 hover:text-white'
            }`}
        >
          جميع المتابعات
        </button>
        <button
          onClick={() => setTab('due_today')}
          className={`pb-3 px-4 border-b-2 transition-all ${tab === 'due_today'
            ? 'border-brand-500 text-brand-400'
            : 'border-transparent text-slate-400 hover:text-white'
            }`}
        >
          متابعات اليوم (Due Today)
        </button>
        <button
          onClick={() => setTab('overdue')}
          className={`pb-3 px-4 border-b-2 transition-all flex items-center gap-1.5 ${tab === 'overdue'
            ? 'border-rose-500 text-rose-400'
            : 'border-transparent text-rose-400/70 hover:text-rose-400'
            }`}
        >
          <span>المتأخرات (Overdue)</span>
          <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse"></span>
        </button>
        <button
          onClick={() => setTab('completed')}
          className={`pb-3 px-4 border-b-2 transition-all ${tab === 'completed'
            ? 'border-emerald-500 text-emerald-400'
            : 'border-transparent text-slate-400 hover:text-white'
            }`}
        >
          المكتملة (Completed)
        </button>
      </div>

      {/* Today's appointments (from the Calendar) */}
      {showAppointments && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-brand-300 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5" />
              مواعيد ومعاينات اليوم ({todayAppointments.length})
            </h3>
            <button
              onClick={() => navigate('/calendar')}
              className="text-[11px] text-slate-400 hover:text-white"
            >
              فتح التقويم
            </button>
          </div>
          {todayAppointments.map((a) => (
            <div
              key={`appt-${a.id}`}
              className="p-4 rounded-2xl border bg-brand-500/5 border-brand-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="flex items-start gap-3.5">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 bg-brand-500/20 text-brand-400">
                  <Phone className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h4
                      onClick={() => navigate(`/leads/${a.lead_id}`)}
                      className="font-bold text-sm text-white hover:text-brand-400 cursor-pointer"
                    >
                      {a.lead_name}
                    </h4>
                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                      {a.appointment_type}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30">
                      موعد اليوم
                    </span>
                  </div>
                  <p className="text-xs text-slate-200 font-medium mt-1">{a.title}</p>
                  <div className="flex items-center gap-3 text-[11px] text-slate-400 mt-2">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(a.start_time).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    {a.location && (
                      <>
                        <span>•</span>
                        <span>{a.location}</span>
                      </>
                    )}
                    <span>•</span>
                    <span>المستشار: {a.user_name}</span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => navigate(`/leads/${a.lead_id}`)}
                className="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors shrink-0"
              >
                فتح العميل
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Follow-ups List */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-20 text-center text-slate-400 text-xs animate-pulse">
            جاري تحميل المتابعات...
          </div>
        ) : followups.length === 0 ? (
          showAppointments ? null : (
            <div className="py-20 text-center text-slate-400 text-xs bg-slate-900 rounded-3xl border border-slate-800">
              لا توجد متابعات مطابقة في هذا التصنيف.
            </div>
          )
        ) : (
          followups.map((f) => (
            <div
              key={f.id}
              className={`p-4 rounded-2xl border transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-lg ${f.is_overdue
                ? 'bg-rose-500/5 border-rose-500/30 hover:border-rose-500/50'
                : f.is_due_today
                  ? 'bg-brand-500/5 border-brand-500/30 hover:border-brand-500/50'
                  : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                }`}
            >
              <div className="flex items-start gap-3.5">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 font-bold ${f.is_overdue
                  ? 'bg-rose-500/20 text-rose-400'
                  : f.status === 'COMPLETED'
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-brand-500/20 text-brand-400'
                  }`}>
                  {f.status === 'COMPLETED' ? (
                    <CheckCircle2 className="w-5 h-5" />
                  ) : f.is_overdue ? (
                    <AlertCircle className="w-5 h-5" />
                  ) : (
                    <Clock className="w-5 h-5" />
                  )}
                </div>

                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h4
                      onClick={() => navigate(`/leads/${f.lead_id}`)}
                      className="font-bold text-sm text-white hover:text-brand-400 cursor-pointer"
                    >
                      {f.lead_name}
                    </h4>
                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-300">
                      {f.follow_up_type}
                    </span>
                    {f.is_overdue && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                        متأخرة!
                      </span>
                    )}
                    {f.is_due_today && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30">
                        مستحقة اليوم
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-slate-200 font-medium mt-1">{f.purpose}</p>
                  {f.notes && <p className="text-[11px] text-slate-400 mt-0.5">{f.notes}</p>}

                  <div className="flex items-center gap-3 text-[11px] text-slate-400 mt-2">
                    <span>المستشار: {f.assigned_user_name}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      تاريخ الاستحقاق: {new Date(f.due_date).toLocaleString('ar-EG')}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex items-center gap-2 shrink-0">
                {f.status !== 'COMPLETED' && (
                  <button
                    onClick={() => {
                      setSelectedFollowup(f);
                      setCompleteModalOpen(true);
                    }}
                    className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md transition-all"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>إتمام وتسجيل النتيجة</span>
                  </button>
                )}

                <button
                  onClick={() => navigate(`/leads/${f.lead_id}`)}
                  className="px-3 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
                >
                  فتح العميل
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Complete Follow-up Modal */}
      {completeModalOpen && selectedFollowup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl relative text-start">
            <h3 className="font-bold text-base text-white mb-1">إتمام المتابعة وتسجيل النتيجة</h3>
            <p className="text-xs text-slate-400 mb-4">
              العميل: <strong className="text-white">{selectedFollowup.lead_name}</strong> - الغرض: {selectedFollowup.purpose}
            </p>

            <form onSubmit={handleCompleteSubmit} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-300 mb-1 font-semibold">نتيجة التواصل *</label>
                <input
                  type="text"
                  required
                  value={completionOutcome}
                  onChange={(e) => setCompletionOutcome(e.target.value)}
                  placeholder="مثال: تم الاتصال، العميل مستعد للمعاينة الأحد القادم"
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">ملاحظات تفصيلية</label>
                <textarea
                  rows={2}
                  value={completionNotes}
                  onChange={(e) => setCompletionNotes(e.target.value)}
                  placeholder="تفاصيل المكالمة وملاحظات المستشار..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                />
              </div>

              {/* Schedule next task toggle */}
              <div className="p-3 rounded-2xl bg-slate-800/60 border border-slate-700/60 space-y-2.5">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={scheduleNext}
                    onChange={(e) => setScheduleNext(e.target.checked)}
                    className="w-4 h-4 rounded text-brand-600 focus:ring-0 bg-slate-700 border-slate-600"
                  />
                  <span className="font-bold text-white text-xs">جدولة المتابعة القادمة فوراً (Smart Next Step)</span>
                </label>

                {scheduleNext && (
                  <div className="space-y-2 pt-2 border-t border-slate-700/60 animate-in fade-in">
                    <div>
                      <label className="block text-slate-400 text-[11px] mb-1">الغرض من المتابعة القادمة</label>
                      <input
                        type="text"
                        value={nextPurpose}
                        onChange={(e) => setNextPurpose(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 text-[11px] mb-1">موعد المتابعة القادمة</label>
                      <input
                        type="datetime-local"
                        value={nextDueDate}
                        onChange={(e) => setNextDueDate(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100 text-xs"
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="pt-3 flex justify-end gap-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setCompleteModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md"
                >
                  {submitting ? 'جاري الإتمام...' : 'إتمام المتابعة'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};