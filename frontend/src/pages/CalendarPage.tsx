import React, { useEffect, useState } from 'react';
import {
  Calendar as CalendarIcon, Clock, Plus, MapPin,
  CheckCircle2, AlertCircle, Building2, User, Phone,
  AlertTriangle, Filter, Sparkles, ChevronRight, ChevronLeft,
  X, Check, List, CalendarDays, Eye
} from 'lucide-react';
import { api } from '../api/client';
import {
  UnifiedCalendarEvent, CalendarDailyBriefing, Lead
} from '../types';

export const CalendarPage: React.FC = () => {
  const [events, setEvents] = useState<UnifiedCalendarEvent[]>([]);
  const [briefing, setBriefing] = useState<CalendarDailyBriefing | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  // Calendar Views
  const [viewMode, setViewMode] = useState<'day' | 'week' | 'month' | 'agenda'>('agenda');
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    const d = new Date();
    return d.toISOString().split('T')[0];
  });

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [myEventsOnly, setMyEventsOnly] = useState<boolean>(false);

  // Modals
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<UnifiedCalendarEvent | null>(null);
  const [eventDetailsOpen, setEventDetailsOpen] = useState(false);

  // New appointment form state
  const [leadId, setLeadId] = useState('');
  const [title, setTitle] = useState('معاينة موقع مع العميل');
  const [appointmentType, setAppointmentType] = useState('Property Visit');
  const [startTime, setStartTime] = useState(`${selectedDate}T11:00`);
  const [endTime, setEndTime] = useState(`${selectedDate}T12:30`);
  const [location, setLocation] = useState('موقع كمبوند The Crest، التجمع الخامس');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchData = () => {
    setLoading(true);

    // Calculate date ranges based on view
    const current = new Date(selectedDate);
    let startD = new Date(current);
    let endD = new Date(current);

    if (viewMode === 'day') {
      startD.setHours(0, 0, 0, 0);
      endD.setHours(23, 59, 59, 999);
    } else if (viewMode === 'week') {
      const day = current.getDay();
      startD.setDate(current.getDate() - day);
      startD.setHours(0, 0, 0, 0);
      endD.setDate(startD.getDate() + 6);
      endD.setHours(23, 59, 59, 999);
    } else if (viewMode === 'month') {
      startD = new Date(current.getFullYear(), current.getMonth(), 1);
      endD = new Date(current.getFullYear(), current.getMonth() + 1, 0, 23, 59, 59);
    } else {
      // Agenda: +/- 30 days
      startD.setDate(current.getDate() - 7);
      endD.setDate(current.getDate() + 30);
    }

    let params = `start_date=${startD.toISOString()}&end_date=${endD.toISOString()}&my_events_only=${myEventsOnly}`;
    if (typeFilter) params += `&event_type=${encodeURIComponent(typeFilter)}`;

    Promise.all([
      api.get<UnifiedCalendarEvent[]>(`/calendar/events?${params}`),
      api.get<CalendarDailyBriefing>(`/calendar/briefing?target_date=${selectedDate}`),
      api.get<Lead[]>('/leads')
    ])
      .then(([evts, brf, lds]) => {
        setEvents(evts);
        setBriefing(brf);
        setLeads(lds);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, [selectedDate, viewMode, typeFilter, myEventsOnly]);

  const handleCreateAppointment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!leadId) return;
    setError('');
    setSubmitting(true);

    try {
      await api.post('/appointments', {
        lead_id: parseInt(leadId),
        title,
        appointment_type: appointmentType,
        start_time: `${startTime}:00`,
        end_time: `${endTime}:00`,
        location,
        notes,
      });

      setModalOpen(false);
      fetchData();
    } catch (err: any) {
      setError(err.message || 'فشل جدولة الموعد');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDateShift = (deltaDays: number) => {
    const d = new Date(selectedDate);
    d.setDate(d.getDate() + deltaDays);
    setSelectedDate(d.toISOString().split('T')[0]);
  };

  const eventTypeLabels: Record<string, { label: string; colorClass: string; bgClass: string }> = {
    'Task': { label: 'مهمة عمل', colorClass: 'text-emerald-400', bgClass: 'bg-emerald-500/10 border-emerald-500/30' },
    'Phone Call': { label: 'مكالمة هاتفية', colorClass: 'text-amber-400', bgClass: 'bg-amber-500/10 border-amber-500/30' },
    'Office Meeting': { label: 'اجتماع بالمكتب', colorClass: 'text-blue-400', bgClass: 'bg-blue-500/10 border-blue-500/30' },
    'Property Visit': { label: 'معاينة ميدانية', colorClass: 'text-purple-400', bgClass: 'bg-purple-500/10 border-purple-500/30' },
    'Client Meeting': { label: 'مقابلة عميل', colorClass: 'text-cyan-400', bgClass: 'bg-cyan-500/10 border-cyan-500/30' },
  };

  return (
    <div className="space-y-6 text-start">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white flex items-center gap-2">
            <CalendarIcon className="w-6 h-6 text-brand-400" />
            <span>التقويم الموحد والمواعيد (Unified Calendar & Events)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            عرض موحد وشامل لكافة المواعيد، المعاينات، والمهام مع كشف تضارب الجداول
          </p>
        </div>

        <button
          onClick={() => {
            setError('');
            setModalOpen(true);
          }}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-lg shadow-brand-600/20 shrink-0"
        >
          <Plus className="w-4 h-4" />
          <span>حجز موعد / معاينة جديدة</span>
        </button>
      </div>

      {/* 1. Dynamic Daily Briefing Card */}
      {briefing && (
        <div className="p-5 rounded-3xl bg-gradient-to-r from-brand-950/70 via-slate-900 to-slate-900 border border-brand-500/20 shadow-xl relative overflow-hidden">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase bg-brand-500/20 text-brand-300 border border-brand-500/30 flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-brand-400 animate-spin" />
                  الملخص اليومي للتقويم (Daily Agenda Briefing)
                </span>
                <span className="text-xs text-slate-400 font-mono">بتوقيت القاهرة: {briefing.selected_date}</span>
              </div>
              <h3 className="text-base sm:text-lg font-bold text-white">
                {briefing.cairo_greeting}! {briefing.summary_text}
              </h3>
              {briefing.attention_items.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {briefing.attention_items.map((item, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs bg-slate-800 text-amber-300 border border-amber-500/30 font-semibold"
                    >
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center gap-2 self-end md:self-center shrink-0">
              <div className="p-3 rounded-2xl bg-slate-800/80 border border-slate-700 text-center min-w-[85px]">
                <p className="text-[10px] text-slate-400 font-bold">المواعيد</p>
                <p className="text-base font-black text-white mt-0.5">{briefing.appointments_count}</p>
              </div>
              <div className="p-3 rounded-2xl bg-slate-800/80 border border-slate-700 text-center min-w-[85px]">
                <p className="text-[10px] text-slate-400 font-bold">المهام</p>
                <p className="text-base font-black text-emerald-400 mt-0.5">{briefing.tasks_count}</p>
              </div>
              {briefing.conflicts_count > 0 && (
                <div className="p-3 rounded-2xl bg-rose-950/50 border border-rose-500/30 text-center min-w-[85px]">
                  <p className="text-[10px] text-rose-300 font-bold">تضاربات</p>
                  <p className="text-base font-black text-rose-400 mt-0.5">{briefing.conflicts_count}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 2. Calendar View Switcher & Date Controls Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 p-4 rounded-3xl bg-slate-900 border border-slate-800 shadow-md">
        {/* Date Navigator */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleDateShift(-1)}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            title="اليوم السابق"
          >
            <ChevronRight className="w-4 h-4" />
          </button>

          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs font-bold text-white focus:outline-none focus:border-brand-500"
          />

          <button
            onClick={() => handleDateShift(1)}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            title="اليوم التالي"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <button
            onClick={() => setSelectedDate(new Date().toISOString().split('T')[0])}
            className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
          >
            اليوم
          </button>
        </div>

        {/* View Mode Switcher */}
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-2xl border border-slate-800 text-xs font-bold self-start md:self-auto">
          <button
            onClick={() => setViewMode('day')}
            className={`px-3 py-1.5 rounded-xl transition-all ${viewMode === 'day' ? 'bg-brand-600 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}
          >
            يومي (Day)
          </button>
          <button
            onClick={() => setViewMode('week')}
            className={`px-3 py-1.5 rounded-xl transition-all ${viewMode === 'week' ? 'bg-brand-600 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}
          >
            أسبوعي (Week)
          </button>
          <button
            onClick={() => setViewMode('month')}
            className={`px-3 py-1.5 rounded-xl transition-all ${viewMode === 'month' ? 'bg-brand-600 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}
          >
            شهري (Month)
          </button>
          <button
            onClick={() => setViewMode('agenda')}
            className={`px-3 py-1.5 rounded-xl transition-all ${viewMode === 'agenda' ? 'bg-brand-600 text-white shadow-md' : 'text-slate-400 hover:text-white'}`}
          >
            جدول زمني (Agenda)
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-brand-500"
          >
            <option value="">كافة أنواع الفعاليات</option>
            <option value="Task">المهام (Tasks)</option>
            <option value="Phone Call">المكالمات الهاتفية</option>
            <option value="Office Meeting">المقابلات المكتبية</option>
            <option value="Property Visit">المعاينات الميدانية</option>
            <option value="Client Meeting">مقابلات العملاء</option>
          </select>

          <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={myEventsOnly}
              onChange={(e) => setMyEventsOnly(e.target.checked)}
              className="rounded bg-slate-950 border-slate-800 text-brand-600 focus:ring-0"
            />
            <span>فعالياتي فقط</span>
          </label>
        </div>
      </div>

      {/* 3. Event Conflict Warning Banner */}
      {events.some(e => e.has_conflict) && (
        <div className="p-4 rounded-2xl bg-amber-950/30 border border-amber-500/40 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-bold text-amber-300">تنبيه: تم رصد تداخل وتضارب في جدول المواعيد</p>
            <p className="text-slate-400">
              يوجد مواعيد متزامنة لنفس الموظف المكلف. تم تمييز هذه المواعيد بعلامة تحذيرية صفراء لإمكانية إعادة تنظيمها بدون إيقاف العمل.
            </p>
          </div>
        </div>
      )}

      {/* 4. Unified Events Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {loading ? (
          <div className="col-span-full py-20 text-center text-slate-400 text-xs animate-pulse">
            جاري تحميل جدول المواعيد والمهام الموحد...
          </div>
        ) : events.length === 0 ? (
          <div className="col-span-full py-20 text-center text-slate-400 text-xs bg-slate-900 rounded-3xl border border-slate-800">
            لا توجد فعاليات أو مهام مجدولة في هذا التاريخ.
          </div>
        ) : (
          events.map((evt) => {
            const meta = eventTypeLabels[evt.event_type] || {
              label: evt.event_type,
              colorClass: 'text-brand-400',
              bgClass: 'bg-brand-500/10 border-brand-500/30'
            };

            return (
              <div
                key={evt.id}
                onClick={() => {
                  setSelectedEvent(evt);
                  setEventDetailsOpen(true);
                }}
                className={`p-5 rounded-3xl bg-slate-900 border transition-all hover:border-slate-700 shadow-xl space-y-3 flex flex-col justify-between cursor-pointer group ${evt.has_conflict
                  ? 'border-amber-500/50 hover:border-amber-500'
                  : 'border-slate-800'
                  }`}
              >
                <div>
                  <div className="flex items-start justify-between">
                    <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${meta.bgClass} ${meta.colorClass}`}>
                      {meta.label}
                    </span>

                    <div className="flex items-center gap-1.5">
                      {evt.has_conflict && (
                        <span
                          className="flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40"
                          title={evt.conflict_notes || 'تضارب زمني'}
                        >
                          <AlertTriangle className="w-3 h-3 text-amber-400" />
                          <span>تضارب</span>
                        </span>
                      )}
                      <span className="text-[10px] font-semibold text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
                        {evt.status}
                      </span>
                    </div>
                  </div>

                  <h3 className="font-bold text-base text-white mt-2 group-hover:text-brand-300 transition-colors">
                    {evt.title}
                  </h3>

                  {evt.lead_name ? (
                    <p className="text-xs text-brand-400 font-semibold mt-0.5 flex items-center gap-1">
                      <User className="w-3.5 h-3.5" />
                      <span>العميل: {evt.lead_name}</span>
                    </p>
                  ) : (
                    <p className="text-xs text-slate-500 mt-0.5">مهمة شخصية بدون عميل</p>
                  )}

                  <div className="space-y-1.5 mt-3 pt-3 border-t border-slate-800/80 text-xs">
                    <div className="flex items-center gap-2 text-slate-300">
                      <Clock className="w-3.5 h-3.5 text-brand-400" />
                      <span>
                        {new Date(evt.start_time).toLocaleDateString('ar-EG', { weekday: 'short', month: 'numeric', day: 'numeric' })} | {new Date(evt.start_time).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })} - {new Date(evt.end_time).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>

                    {evt.location && (
                      <div className="flex items-center gap-2 text-slate-400">
                        <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                        <span className="truncate">{evt.location}</span>
                      </div>
                    )}

                    {evt.description && (
                      <p className="text-[11px] text-slate-400 p-2 rounded-xl bg-slate-950/60 border border-slate-800/80 mt-2 line-clamp-2">
                        {evt.description}
                      </p>
                    )}
                  </div>
                </div>

                <div className="pt-2 text-[11px] text-slate-500 border-t border-slate-800 flex items-center justify-between">
                  <span>المكلف: {evt.assigned_user_name}</span>
                  <span className="text-[10px] text-slate-600 font-mono">#{evt.id}</span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Event Details Modal */}
      {eventDetailsOpen && selectedEvent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-lg w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full border ${eventTypeLabels[selectedEvent.event_type]?.bgClass}`}>
                  {eventTypeLabels[selectedEvent.event_type]?.label || selectedEvent.event_type}
                </span>
                <h3 className="text-base font-bold text-white">تفاصيل الفعالية</h3>
              </div>
              <button onClick={() => setEventDetailsOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              {selectedEvent.has_conflict && (
                <div className="p-3 rounded-2xl bg-amber-950/40 border border-amber-500/40 text-amber-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>{selectedEvent.conflict_notes || 'يوجد تضارب في موعد هذه الفعالية مع موعد آخر'}</span>
                </div>
              )}

              <div>
                <p className="text-slate-400">العنوان / الإجراء</p>
                <p className="text-base font-bold text-white mt-0.5">{selectedEvent.title}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-slate-400">وقت البدء</p>
                  <p className="font-semibold text-white mt-0.5">
                    {new Date(selectedEvent.start_time).toLocaleString('ar-EG')}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400">وقت الانتهاء</p>
                  <p className="font-semibold text-white mt-0.5">
                    {new Date(selectedEvent.end_time).toLocaleString('ar-EG')}
                  </p>
                </div>
              </div>

              {selectedEvent.lead_name && (
                <div className="p-3 rounded-2xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                  <div>
                    <p className="text-slate-400">العميل المرتبط</p>
                    <p className="font-bold text-white mt-0.5">{selectedEvent.lead_name}</p>
                    {selectedEvent.lead_phone && <p className="text-slate-400 font-mono mt-0.5">{selectedEvent.lead_phone}</p>}
                  </div>
                  {selectedEvent.lead_id && (
                    <a
                      href={`/leads/${selectedEvent.lead_id}`}
                      className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-brand-400 font-bold"
                    >
                      فتح ملف العميل
                    </a>
                  )}
                </div>
              )}

              {selectedEvent.location && (
                <div>
                  <p className="text-slate-400">المكان / الموقع</p>
                  <p className="font-semibold text-white mt-0.5 flex items-center gap-1.5">
                    <MapPin className="w-4 h-4 text-brand-400" />
                    <span>{selectedEvent.location}</span>
                  </p>
                </div>
              )}

              {selectedEvent.description && (
                <div>
                  <p className="text-slate-400">الملاحظات والتعليمات</p>
                  <p className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 mt-1 whitespace-pre-wrap">
                    {selectedEvent.description}
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                onClick={() => setEventDetailsOpen(false)}
                className="px-4 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-800 text-xs font-bold"
              >
                إغلاق
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Appointment Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-lg w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Plus className="w-5 h-5 text-brand-400" />
                <span>حجز موعد أو معاينة جديدة</span>
              </h3>
              <button onClick={() => setModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            {error && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
                {error}
              </div>
            )}

            <form onSubmit={handleCreateAppointment} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-bold mb-1">العميل المرتبط</label>
                <select
                  required
                  value={leadId}
                  onChange={(e) => setLeadId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                >
                  <option value="">اختر عميلاً من القائمة...</option>
                  {leads.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.full_name} ({l.phone})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-bold mb-1">عنوان الموعد</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-bold mb-1">نوع الموعد</label>
                  <select
                    value={appointmentType}
                    onChange={(e) => setAppointmentType(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                  >
                    <option value="Property Visit">معاينة موقع (Property Visit)</option>
                    <option value="Office Meeting">مقابلة مكتبية (Office Meeting)</option>
                    <option value="Client Meeting">مقابلة عميل خارج المكتب</option>
                    <option value="Video Call">مكالمة فيديو زووم / تيمز</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 font-bold mb-1">الموقع أو الرابط</label>
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-bold mb-1">وقت البدء (بتوقيت القاهرة)</label>
                  <input
                    type="datetime-local"
                    required
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-bold mb-1">وقت الانتهاء (بتوقيت القاهرة)</label>
                  <input
                    type="datetime-local"
                    required
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-bold mb-1">ملاحظات التحضير للموعد</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="أي تفاصيل تخص العميل، أو الوحدات المطلوب معاينتها..."
                  rows={3}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-800"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-bold"
                >
                  {submitting ? 'جاري الحفظ...' : 'تأكيد الحجز'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
