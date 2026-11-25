import React, { useEffect, useState } from 'react';
import {
  CheckSquare, Plus, Clock, AlertCircle, CheckCircle2,
  Phone, Calendar, User, ArrowRight, RefreshCw, MessageSquare,
  Search, Filter, AlertTriangle, ArrowUpDown, MoreVertical,
  Edit2, Eye, Check, X, ShieldAlert, Sparkles, ChevronRight, Activity as ActivityIcon
} from 'lucide-react';
import { api } from '../api/client';
import {
  FollowUp, FollowUpBriefing, FollowUpStats, PriorityLevel,
  FollowUpStatus, Activity
} from '../types';
import { useNavigate } from 'react-router-dom';

interface MyTasksPageProps {
  teamMode?: boolean;
}

export const MyTasksPage: React.FC<MyTasksPageProps> = ({ teamMode = false }) => {
  const [tasks, setTasks] = useState<FollowUp[]>([]);
  const [briefing, setBriefing] = useState<FollowUpBriefing | null>(null);
  const [stats, setStats] = useState<FollowUpStats>({
    total: 0, overdue: 0, due_today: 0, upcoming: 0, completed: 0
  });
  const [loading, setLoading] = useState(true);

  // 6 dedicated sections/tabs
  const [section, setSection] = useState<'today' | 'overdue' | 'upcoming' | 'recent' | 'completed' | 'all'>('today');

  // Search & Filters
  const [search, setSearch] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  // Modals
  const [selectedTask, setSelectedTask] = useState<FollowUp | null>(null);
  const [detailsModalOpen, setDetailsModalOpen] = useState(false);
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [rescheduleModalOpen, setRescheduleModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [taskActivities, setTaskActivities] = useState<Activity[]>([]);

  // Action states
  const [completionOutcome, setCompletionOutcome] = useState('تم التواصل والمتابعة بنجاح');
  const [completionNotes, setCompletionNotes] = useState('');
  const [newDueDate, setNewDueDate] = useState('');
  const [newPriority, setNewPriority] = useState<PriorityLevel>('MEDIUM');
  const [submitting, setSubmitting] = useState(false);

  // New task form
  const [newPurpose, setNewPurpose] = useState('');
  const [newTaskDueDate, setNewTaskDueDate] = useState('');
  const [newTaskType, setNewTaskType] = useState('Task');
  const [newTaskPriority, setNewTaskPriority] = useState<PriorityLevel>('MEDIUM');
  const [newTaskNotes, setNewTaskNotes] = useState('');

  const navigate = useNavigate();

  const fetchBriefingAndStats = () => {
    api.get<FollowUpBriefing>('/followups/my-briefing')
      .then(setBriefing)
      .catch(console.error);

    api.get<FollowUpStats>(`/followups/my-stats?assigned_to_me=${!teamMode}`)
      .then(setStats)
      .catch(console.error);
  };

  const fetchTasks = () => {
    setLoading(true);
    let params = `section=${section}&assigned_to_me=${!teamMode}`;
    if (search.trim()) params += `&search=${encodeURIComponent(search.trim())}`;
    if (priorityFilter) params += `&priority=${priorityFilter}`;
    if (statusFilter) params += `&status=${statusFilter}`;
    if (typeFilter) params += `&task_type=${typeFilter}`;

    api.get<FollowUp[]>(`/followups?${params}`)
      .then(setTasks)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchBriefingAndStats();
  }, [teamMode]);

  useEffect(() => {
    fetchTasks();
  }, [section, priorityFilter, statusFilter, typeFilter, teamMode]);

  // Handle Search Debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchTasks();
    }, 350);
    return () => clearTimeout(timer);
  }, [search]);

  // Actions
  const handleCompleteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask) return;
    setSubmitting(true);
    try {
      await api.post(`/followups/${selectedTask.id}/complete`, {
        completion_outcome: completionOutcome,
        notes: completionNotes,
      });
      setCompleteModalOpen(false);
      setSelectedTask(null);
      setCompletionNotes('');
      fetchTasks();
      fetchBriefingAndStats();
    } catch (err: any) {
      alert(`خطأ: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRescheduleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask || !newDueDate) return;
    setSubmitting(true);
    try {
      await api.patch(`/followups/${selectedTask.id}`, {
        due_date: `${newDueDate}:00`,
      });
      setRescheduleModalOpen(false);
      setSelectedTask(null);
      fetchTasks();
      fetchBriefingAndStats();
    } catch (err: any) {
      alert(`خطأ: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleQuickStatusChange = async (task: FollowUp, newStatus: FollowUpStatus) => {
    try {
      await api.patch(`/followups/${task.id}`, {
        status: newStatus,
      });
      fetchTasks();
      fetchBriefingAndStats();
    } catch (err: any) {
      alert(`خطأ في تغيير الحالة: ${err.message}`);
    }
  };

  const handlePriorityChange = async (task: FollowUp, p: PriorityLevel) => {
    try {
      await api.patch(`/followups/${task.id}`, {
        priority: p,
      });
      fetchTasks();
    } catch (err: any) {
      alert(`خطأ: ${err.message}`);
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPurpose || !newTaskDueDate) return;
    setSubmitting(true);
    try {
      await api.post('/followups', {
        purpose: newPurpose,
        due_date: `${newTaskDueDate}:00`,
        follow_up_type: newTaskType,
        priority: newTaskPriority,
        notes: newTaskNotes,
      });
      setCreateModalOpen(false);
      setNewPurpose('');
      setNewTaskDueDate('');
      setNewTaskNotes('');
      fetchTasks();
      fetchBriefingAndStats();
    } catch (err: any) {
      alert(`خطأ: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const openActivity = (task: FollowUp) => {
    setSelectedTask(task);
    api.get<Activity[]>(`/followups/${task.id}/activity`)
      .then(setTaskActivities)
      .catch(() => setTaskActivities([]));
    setActivityModalOpen(true);
  };

  return (
    <div className="space-y-6 text-start">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white flex items-center gap-2">
            <CheckSquare className="w-6 h-6 text-brand-400" />
            <span>{teamMode ? 'إدارة مهام ومتابعات الفريق' : 'مركز إدارة مهامي الشخصية (My Tasks Center)'}</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            {teamMode
              ? 'متابعة كافة مهام فريق المبيعات، ومراقبة المتأخرات والمواعيد'
              : 'تنظيم جدول أعمالك اليومي، إنجاز المهام، وإعادة جدولتها بدقة بتوقيت القاهرة'}
          </p>
        </div>

        <button
          onClick={() => setCreateModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-lg shadow-brand-600/20 shrink-0"
        >
          <Plus className="w-4 h-4" />
          <span>إضافة مهمة جديدة</span>
        </button>
      </div>

      {/* 1. Dynamic Daily Briefing Card */}
      {briefing && (
        <div className="p-5 rounded-3xl bg-gradient-to-r from-brand-950/60 via-slate-900 to-slate-900 border border-brand-500/20 shadow-xl relative overflow-hidden">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase bg-brand-500/20 text-brand-300 border border-brand-500/30 flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-brand-400 animate-spin" />
                  الملخص اليومي الذكي (Cairo Daily Briefing)
                </span>
                <span className="text-xs text-slate-400 font-mono">{briefing.cairo_time}</span>
              </div>
              <h3 className="text-base sm:text-lg font-bold text-white">
                {briefing.greeting}! {briefing.attention_summary}
              </h3>
              {briefing.actionable_items.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-1">
                  {briefing.actionable_items.map((item, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs bg-slate-800/80 text-amber-300 border border-amber-500/30"
                    >
                      <AlertTriangle className="w-3 h-3 text-amber-400" />
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="flex items-center gap-3 self-end md:self-center shrink-0">
              <div className="p-3 rounded-2xl bg-slate-800/60 border border-slate-700/60 text-center min-w-[90px]">
                <p className="text-[10px] text-slate-400 font-bold">أول موعد اليوم</p>
                <p className="text-sm font-black text-white mt-0.5">{briefing.earliest_task_time || 'لا يوجد'}</p>
              </div>
              <div className="p-3 rounded-2xl bg-rose-950/40 border border-rose-500/30 text-center min-w-[90px]">
                <p className="text-[10px] text-rose-300 font-bold">المتأخرات</p>
                <p className="text-sm font-black text-rose-400 mt-0.5">{briefing.overdue_count}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 2. Five Statistics Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <button
          onClick={() => setSection('all')}
          className={`p-4 rounded-2xl border text-start transition-all ${section === 'all'
            ? 'bg-slate-800 border-brand-500 shadow-lg shadow-brand-500/10'
            : 'bg-slate-900 border-slate-800 hover:border-slate-700'
            }`}
        >
          <p className="text-xs text-slate-400 font-semibold">إجمالي المهام</p>
          <p className="text-2xl font-black text-white mt-1">{stats.total}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">كافة السجلات</p>
        </button>

        <button
          onClick={() => setSection('overdue')}
          className={`p-4 rounded-2xl border text-start transition-all ${section === 'overdue'
            ? 'bg-rose-950/40 border-rose-500 shadow-lg shadow-rose-500/10'
            : 'bg-slate-900 border-slate-800 hover:border-slate-700'
            }`}
        >
          <div className="flex items-center justify-between">
            <p className="text-xs text-rose-300 font-semibold">المتأخرات</p>
            {stats.overdue > 0 && <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse"></span>}
          </div>
          <p className="text-2xl font-black text-rose-400 mt-1">{stats.overdue}</p>
          <p className="text-[10px] text-rose-400/70 mt-0.5">تحتاج معالجة فورية</p>
        </button>

        <button
          onClick={() => setSection('today')}
          className={`p-4 rounded-2xl border text-start transition-all ${section === 'today'
            ? 'bg-amber-950/40 border-amber-500 shadow-lg shadow-amber-500/10'
            : 'bg-slate-900 border-slate-800 hover:border-slate-700'
            }`}
        >
          <p className="text-xs text-amber-300 font-semibold">مستحقة اليوم</p>
          <p className="text-2xl font-black text-amber-400 mt-1">{stats.due_today}</p>
          <p className="text-[10px] text-amber-400/70 mt-0.5">جدول اليوم الحالي</p>
        </button>

        <button
          onClick={() => setSection('upcoming')}
          className={`p-4 rounded-2xl border text-start transition-all ${section === 'upcoming'
            ? 'bg-blue-950/40 border-blue-500 shadow-lg shadow-blue-500/10'
            : 'bg-slate-900 border-slate-800 hover:border-slate-700'
            }`}
        >
          <p className="text-xs text-blue-300 font-semibold">القادمة (Upcoming)</p>
          <p className="text-2xl font-black text-blue-400 mt-1">{stats.upcoming}</p>
          <p className="text-[10px] text-blue-400/70 mt-0.5">خلال الأيام القادمة</p>
        </button>

        <button
          onClick={() => setSection('completed')}
          className={`p-4 rounded-2xl border text-start transition-all col-span-2 sm:col-span-1 ${section === 'completed'
            ? 'bg-emerald-950/40 border-emerald-500 shadow-lg shadow-emerald-500/10'
            : 'bg-slate-900 border-slate-800 hover:border-slate-700'
            }`}
        >
          <p className="text-xs text-emerald-300 font-semibold">المكتملة</p>
          <p className="text-2xl font-black text-emerald-400 mt-1">{stats.completed}</p>
          <p className="text-[10px] text-emerald-400/70 mt-0.5">تم إنجازها بنجاح</p>
        </button>
      </div>

      {/* 3. Dedicated Section Tabs */}
      <div className="flex border-b border-slate-800 overflow-x-auto space-x-2 space-x-reverse text-xs font-bold scrollbar-none">
        <button
          onClick={() => setSection('today')}
          className={`pb-3 px-4 border-b-2 whitespace-nowrap transition-all ${section === 'today'
            ? 'border-amber-500 text-amber-400'
            : 'border-transparent text-slate-400 hover:text-white'
            }`}
        >
          مهام اليوم ({stats.due_today})
        </button>
        <button
          onClick={() => setSection('overdue')}
          className={`pb-3 px-4 border-b-2 whitespace-nowrap transition-all flex items-center gap-1.5 ${section === 'overdue'
            ? 'border-rose-500 text-rose-400'
            : 'border-transparent text-slate-400 hover:text-rose-400'
            }`}
        >
          <span>المتأخرات ({stats.overdue})</span>
          {stats.overdue > 0 && <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></span>}
        </button>
        <button
          onClick={() => setSection('upcoming')}
          className={`pb-3 px-4 border-b-2 whitespace-nowrap transition-all ${section === 'upcoming'
            ? 'border-blue-500 text-blue-400'
            : 'border-transparent text-slate-400 hover:text-white'
            }`}
        >
          المستقبلية ({stats.upcoming})
        </button>
        <button
          onClick={() => setSection('recent')}
          className={`pb-3 px-4 border-b-2 whitespace-nowrap transition-all ${section === 'recent'
            ? 'border-brand-500 text-brand-400'
            : 'border-transparent text-slate-400 hover:text-white'
            }`}
        >
          المضافة حديثاً (Recent)
        </button>
        <button
          onClick={() => setSection('completed')}
          className={`pb-3 px-4 border-b-2 whitespace-nowrap transition-all ${section === 'completed'
            ? 'border-emerald-500 text-emerald-400'
            : 'border-transparent text-slate-400 hover:text-white'
            }`}
        >
          المكتملة ({stats.completed})
        </button>
        <button
          onClick={() => setSection('all')}
          className={`pb-3 px-4 border-b-2 whitespace-nowrap transition-all ${section === 'all'
            ? 'border-brand-500 text-brand-400'
            : 'border-transparent text-slate-400 hover:text-white'
            }`}
        >
          جميع المهام ({stats.total})
        </button>
      </div>

      {/* 4. Search & Filter Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 p-3 rounded-2xl bg-slate-900 border border-slate-800">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-500 absolute start-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="بحث باسم المهمة، العميل، الهاتف أو الملاحظات..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-xl ps-9 pe-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-brand-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Priority Filter */}
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-brand-500"
          >
            <option value="">جميع الأولويات</option>
            <option value="URGENT">عاجلة (Urgent)</option>
            <option value="HIGH">عالية (High)</option>
            <option value="MEDIUM">متوسطة (Medium)</option>
            <option value="LOW">منخفضة (Low)</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-brand-500"
          >
            <option value="">كافة الحالات</option>
            <option value="PENDING">معلقة (Pending)</option>
            <option value="IN_PROGRESS">قيد التنفيذ (In Progress)</option>
            <option value="DUE_TODAY">مستحقة اليوم (Due Today)</option>
            <option value="OVERDUE">متأخرة (Overdue)</option>
            <option value="COMPLETED">مكتملة (Completed)</option>
            <option value="RESCHEDULED">مجدولة (Rescheduled)</option>
          </select>

          {/* Task Type Filter */}
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-brand-500"
          >
            <option value="">كل الأنواع</option>
            <option value="Task">مهمة عامة</option>
            <option value="Call">مكالمة هاتفية</option>
            <option value="Meeting">مقابلة</option>
            <option value="WhatsApp">واتساب</option>
            <option value="Visit">معاينة</option>
          </select>

          {(search || priorityFilter || statusFilter || typeFilter) && (
            <button
              onClick={() => {
                setSearch('');
                setPriorityFilter('');
                setStatusFilter('');
                setTypeFilter('');
              }}
              className="p-2 text-xs text-rose-400 hover:text-rose-300 transition-colors"
              title="تفريغ الفلاتر"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* 5. Tasks List / Cards */}
      <div className="space-y-3">
        {loading ? (
          <div className="py-20 text-center text-slate-400 text-xs animate-pulse">
            جاري تحميل المهام...
          </div>
        ) : tasks.length === 0 ? (
          <div className="py-20 text-center text-slate-400 text-xs bg-slate-900 rounded-3xl border border-slate-800">
            لا توجد مهام تطابق المعايير المحددة.
          </div>
        ) : (
          tasks.map((task) => {
            const isOverdue = task.is_overdue && task.status !== 'COMPLETED';
            const isDueToday = task.is_due_today && task.status !== 'COMPLETED';

            const statusColors: Record<string, string> = {
              COMPLETED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
              IN_PROGRESS: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
              OVERDUE: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
              DUE_TODAY: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
              PENDING: 'bg-slate-700/30 text-slate-300 border-slate-700',
              RESCHEDULED: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
              CANCELLED: 'bg-slate-800 text-slate-500 border-slate-700',
            };

            const priorityColors: Record<string, string> = {
              URGENT: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
              HIGH: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
              MEDIUM: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
              LOW: 'bg-slate-700/40 text-slate-400 border-slate-700',
            };

            return (
              <div
                key={task.id}
                className={`p-5 rounded-3xl bg-slate-900 border transition-all hover:border-slate-700 shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4 ${isOverdue
                  ? 'border-rose-500/40 bg-rose-950/10'
                  : isDueToday
                    ? 'border-amber-500/30'
                    : 'border-slate-800'
                  }`}
              >
                {/* Task Details */}
                <div className="space-y-2 flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* Status Badge */}
                    <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${statusColors[task.status] || 'bg-slate-800 text-slate-400'}`}>
                      {task.status === 'COMPLETED' ? 'مكتملة' :
                        task.status === 'IN_PROGRESS' ? 'قيد التنفيذ' :
                          task.status === 'OVERDUE' ? 'متأخرة' :
                            task.status === 'DUE_TODAY' ? 'مستحقة اليوم' :
                              task.status === 'RESCHEDULED' ? 'أعيدت جدولتها' :
                                task.status === 'CANCELLED' ? 'ملغاة' : 'معلقة'}
                    </span>

                    {/* Priority Badge */}
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${priorityColors[task.priority] || ''}`}>
                      {task.priority === 'URGENT' ? 'عاجلة جداً' :
                        task.priority === 'HIGH' ? 'أولوية عالية' :
                          task.priority === 'MEDIUM' ? 'أولوية متوسطة' : 'أولوية عادية'}
                    </span>

                    {/* Type Badge */}
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                      {task.follow_up_type}
                    </span>

                    {/* Creator label if delegated */}
                    {task.created_by_name && task.created_by_id !== task.assigned_user_id && (
                      <span className="text-[10px] text-brand-400 font-semibold bg-brand-500/10 px-2 py-0.5 rounded-full border border-brand-500/20">
                        مهمة من: {task.created_by_name}
                      </span>
                    )}
                  </div>

                  <h3 className="font-bold text-sm sm:text-base text-white truncate">
                    {task.purpose}
                  </h3>

                  <div className="flex flex-wrap items-center gap-y-1 gap-x-4 text-xs text-slate-400">
                    {/* Due Date */}
                    <div className="flex items-center gap-1.5">
                      <Clock className={`w-3.5 h-3.5 ${isOverdue ? 'text-rose-400' : isDueToday ? 'text-amber-400' : 'text-slate-400'}`} />
                      <span className={isOverdue ? 'text-rose-400 font-bold' : isDueToday ? 'text-amber-400 font-bold' : ''}>
                        {new Date(task.due_date).toLocaleString('ar-EG', { dateStyle: 'medium', timeStyle: 'short' })}
                      </span>
                    </div>

                    {/* Customer */}
                    {task.lead_name && task.lead_id ? (
                      <button
                        onClick={() => navigate(`/leads/${task.lead_id}`)}
                        className="flex items-center gap-1.5 text-brand-400 hover:text-brand-300 font-semibold"
                      >
                        <User className="w-3.5 h-3.5" />
                        <span>العميل: {task.lead_name}</span>
                        {task.lead_phone && <span className="text-slate-500 font-mono">({task.lead_phone})</span>}
                      </button>
                    ) : (
                      <div className="flex items-center gap-1.5 text-slate-500">
                        <User className="w-3.5 h-3.5" />
                        <span>مهمة شخصية</span>
                      </div>
                    )}

                    {/* Assignee if teamMode */}
                    {teamMode && (
                      <div className="text-slate-400 text-[11px]">
                        المكلف: <span className="text-white font-semibold">{task.assigned_user_name}</span>
                      </div>
                    )}
                  </div>

                  {task.notes && (
                    <p className="text-xs text-slate-400 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80 line-clamp-2">
                      {task.notes}
                    </p>
                  )}
                </div>

                {/* Task Action Buttons */}
                <div className="flex items-center gap-2 self-end md:self-center shrink-0">
                  {task.status !== 'COMPLETED' ? (
                    <button
                      onClick={() => {
                        setSelectedTask(task);
                        setCompletionNotes('');
                        setCompleteModalOpen(true);
                      }}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20 transition-all"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>إنجاز</span>
                    </button>
                  ) : (
                    <button
                      onClick={() => handleQuickStatusChange(task, 'PENDING')}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>إعادة فتح</span>
                    </button>
                  )}

                  <button
                    onClick={() => {
                      setSelectedTask(task);
                      setNewDueDate(task.due_date.slice(0, 16));
                      setRescheduleModalOpen(true);
                    }}
                    className="p-2 rounded-xl text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
                    title="إعادة جدولة الموعد"
                  >
                    <Calendar className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => {
                      setSelectedTask(task);
                      setDetailsModalOpen(true);
                    }}
                    className="p-2 rounded-xl text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
                    title="تفاصيل المهمة"
                  >
                    <Eye className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => openActivity(task)}
                    className="p-2 rounded-xl text-slate-400 hover:text-brand-400 bg-slate-800 hover:bg-slate-700 transition-colors"
                    title="سجل الأنشطة والمتابعة"
                  >
                    <ActivityIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Complete Task Modal */}
      {completeModalOpen && selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <span>إتمام وإنجاز المهمة (#{selectedTask.id})</span>
            </h3>
            <p className="text-xs text-slate-400">{selectedTask.purpose}</p>

            <form onSubmit={handleCompleteSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-bold mb-1">نتيجة المتابعة (Outcome)</label>
                <select
                  value={completionOutcome}
                  onChange={(e) => setCompletionOutcome(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                >
                  <option value="تم التواصل والمتابعة بنجاح">تم التواصل والمتابعة بنجاح</option>
                  <option value="العميل طلب مهلة للتفكير">العميل طلب مهلة للتفكير</option>
                  <option value="تم تحديد موعد معاينة">تم تحديد موعد معاينة</option>
                  <option value="العميل لم يرد / مغلق">العميل لم يرد / مغلق</option>
                  <option value="تم إرسال العرض والبروشور">تم إرسال العرض والبروشور</option>
                  <option value="أخرى">أخرى</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-bold mb-1">ملاحظات الإنجاز</label>
                <textarea
                  value={completionNotes}
                  onChange={(e) => setCompletionNotes(e.target.value)}
                  placeholder="سجل ما تم الاتفاق عليه أثناء المتابعة..."
                  rows={3}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCompleteModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-800"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
                >
                  {submitting ? 'جاري الحفظ...' : 'تأكيد الإنجاز'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Reschedule Modal */}
      {rescheduleModalOpen && selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Calendar className="w-5 h-5 text-brand-400" />
              <span>إعادة جدولة المهمة (#{selectedTask.id})</span>
            </h3>

            <form onSubmit={handleRescheduleSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-bold mb-1">الموعد الجديد (بتوقيت القاهرة)</label>
                <input
                  type="datetime-local"
                  required
                  value={newDueDate}
                  onChange={(e) => setNewDueDate(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setRescheduleModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-800"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-bold"
                >
                  {submitting ? 'جاري الحفظ...' : 'تأكيد الموعد الجديد'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Task Details Modal */}
      {detailsModalOpen && selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-lg w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white">تفاصيل المهمة #{selectedTask.id}</h3>
              <button onClick={() => setDetailsModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <p className="text-slate-400">عنوان المهمة / الهدف</p>
                <p className="text-sm font-bold text-white mt-0.5">{selectedTask.purpose}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-slate-400">تاريخ ووقت الاستحقاق</p>
                  <p className="font-semibold text-white mt-0.5">
                    {new Date(selectedTask.due_date).toLocaleString('ar-EG')}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400">الحالة الحالية</p>
                  <p className="font-semibold text-brand-400 mt-0.5">{selectedTask.status}</p>
                </div>
              </div>

              {selectedTask.lead_id && (
                <div className="p-3 rounded-2xl bg-slate-950 border border-slate-800">
                  <p className="text-slate-400">العميل المرتبط</p>
                  <p className="font-bold text-white mt-0.5">{selectedTask.lead_name}</p>
                  {selectedTask.lead_phone && <p className="text-slate-400 font-mono mt-0.5">{selectedTask.lead_phone}</p>}
                </div>
              )}

              {selectedTask.notes && (
                <div>
                  <p className="text-slate-400">الملاحظات</p>
                  <p className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-slate-300 mt-1 whitespace-pre-wrap">
                    {selectedTask.notes}
                  </p>
                </div>
              )}

              {selectedTask.completion_outcome && (
                <div>
                  <p className="text-slate-400">نتيجة الإنجاز</p>
                  <p className="font-bold text-emerald-400 mt-0.5">{selectedTask.completion_outcome}</p>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <button
                onClick={() => setDetailsModalOpen(false)}
                className="px-4 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-800 text-xs"
              >
                إغلاق
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Activity History Modal */}
      {activityModalOpen && selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-lg w-full shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <ActivityIcon className="w-5 h-5 text-brand-400" />
                <span>سجل الأنشطة والتفاعل (Activity History)</span>
              </h3>
              <button onClick={() => setActivityModalOpen(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto space-y-2 flex-1 pe-1">
              {taskActivities.length === 0 ? (
                <p className="py-10 text-center text-slate-500 text-xs">لا توجد أنشطة مسجلة بعد لهذا العميل.</p>
              ) : (
                taskActivities.map((act) => (
                  <div key={act.id} className="p-3 rounded-2xl bg-slate-950 border border-slate-800 text-xs space-y-1">
                    <div className="flex items-center justify-between text-slate-400">
                      <span className="font-bold text-brand-400">{act.activity_type}</span>
                      <span className="text-[10px]">{new Date(act.created_at).toLocaleString('ar-EG')}</span>
                    </div>
                    <p className="text-white font-medium">{act.summary}</p>
                    {act.outcome && <p className="text-[11px] text-emerald-400 font-semibold">النتيجة: {act.outcome}</p>}
                    <p className="text-[10px] text-slate-500">بواسطة: {act.user_name || 'مستشار'}</p>
                  </div>
                ))
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-800">
              <button
                onClick={() => setActivityModalOpen(false)}
                className="px-4 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-800 text-xs"
              >
                إغلاق
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create New Task Modal */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Plus className="w-5 h-5 text-brand-400" />
              <span>إضافة مهمة جديدة</span>
            </h3>

            <form onSubmit={handleCreateTask} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-bold mb-1">عنوان المهمة / الإجراء</label>
                <input
                  type="text"
                  required
                  placeholder="مثلاً: مراجعة مسودة العقد أو الاتصال بالعميل"
                  value={newPurpose}
                  onChange={(e) => setNewPurpose(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-bold mb-1">تاريخ ووقت الاستحقاق</label>
                  <input
                    type="datetime-local"
                    required
                    value={newTaskDueDate}
                    onChange={(e) => setNewTaskDueDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-bold mb-1">الأولوية</label>
                  <select
                    value={newTaskPriority}
                    onChange={(e) => setNewTaskPriority(e.target.value as PriorityLevel)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                  >
                    <option value="LOW">منخفضة</option>
                    <option value="MEDIUM">متوسطة</option>
                    <option value="HIGH">عالية</option>
                    <option value="URGENT">عاجلة جداً</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-bold mb-1">نوع المهمة</label>
                <select
                  value={newTaskType}
                  onChange={(e) => setNewTaskType(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                >
                  <option value="Task">مهمة عامة</option>
                  <option value="Call">مكالمة هاتفية</option>
                  <option value="Meeting">مقابلة</option>
                  <option value="WhatsApp">واتساب</option>
                  <option value="Property Visit">معاينة موقع</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-bold mb-1">ملاحظات إضافية</label>
                <textarea
                  value={newTaskNotes}
                  onChange={(e) => setNewTaskNotes(e.target.value)}
                  placeholder="أي تفاصيل أو تعليمات خاصة بالمهمة..."
                  rows={3}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-2.5 text-white focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white bg-slate-800"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-bold"
                >
                  {submitting ? 'جاري الإنشاء...' : 'حفظ المهمة'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

