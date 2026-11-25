import React, { useEffect, useState } from 'react';
import { 
  Users, CheckSquare, Clock, Calendar, TrendingUp, AlertCircle, 
  ArrowUpRight, Building2, Award, Sparkles, PhoneCall, MessageSquare,
  Activity, Target, Shield, CheckCircle2, ChevronRight, Volume2, Bot
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell } from 'recharts';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

const COLORS = ['#0e8ce4', '#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'];

export const DashboardPage: React.FC = () => {
  const { user, t } = useAuth();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    api.get<any>('/dashboard/metrics')
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="py-20 text-center text-slate-400 text-sm animate-pulse">
        جاري تحميل مؤشرات ولوحة التحكم...
      </div>
    );
  }

  const summary = data?.summary || {};
  const isAgent = user?.role === 'SALES_AGENT';
  const isLeader = user?.role === 'TEAM_LEADER';
  const isManager = ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER'].includes(user?.role || '');
  const isAdmin = ['SUPER_ADMIN', 'COMPANY_ADMIN'].includes(user?.role || '');

  const getWorkspaceTitle = () => {
    switch (user?.role) {
      case 'SALES_AGENT':
        return 'مساحة عمل مستشار المبيعات (Agent Workspace)';
      case 'TEAM_LEADER':
        return 'مساحة عمل قائد الفريق (Team Leader Hub)';
      case 'SALES_MANAGER':
        return 'لوحة قيادة إدارة المبيعات (Sales Operations)';
      case 'COMPANY_ADMIN':
        return 'لوحة الإدارة التنفيذية للشركة (Executive Dashboard)';
      case 'SUPER_ADMIN':
        return 'منصة إدارة النظام المركزية (Platform Super Admin)';
      default:
        return 'لوحة التحكم والمتابعة';
    }
  };

  return (
    <div className="space-y-6 text-start">
      {/* ── Top Banner / Role Greeting ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 sm:p-6 rounded-3xl bg-gradient-to-r from-slate-900 via-slate-900 to-slate-800 border border-slate-800 shadow-xl relative overflow-hidden">
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-brand-500/20 text-brand-300 border border-brand-500/30">
              {getWorkspaceTitle()}
            </span>
            <span className="text-xs text-slate-400">
              {data?.company_name || 'Nexora Developments'}
            </span>
          </div>
          <h2 className="text-xl sm:text-2xl font-black text-white">
            مرحباً بك، {user?.full_name} 👋
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            {isAgent
              ? 'إليك عملائك المخصصين، مواعيد المعاينات اليوم، والمتابعات التي تحتاج تواصلاً عاجلاً.'
              : isLeader
              ? 'متابعة شاملة لأداء أعضاء فريقك، توزيع العملاء، ونسب إنجاز المعاينات والمتابعات.'
              : 'نظرة تنفيذية شاملة على مسار صفقات البيع، كفاءة الفرق، ومؤشرات الذكاء الاصطناعي والصوت.'}
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0 z-10">
          <button
            onClick={() => navigate('/leads')}
            className="px-4 py-2 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white transition-all shadow-md shadow-brand-600/20"
          >
            + إضافة عميل
          </button>
          <button
            onClick={() => navigate('/conversations')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-slate-800 text-slate-200 border border-slate-700 hover:text-white transition-all"
          >
            <MessageSquare className="w-3.5 h-3.5 text-brand-400" />
            <span>صندوق المحادثات</span>
            {summary.unread_conversations > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-rose-500 text-white text-[10px] font-bold">
                {summary.unread_conversations}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* ── Smart Business Insights & Evidence-Based Alerts ── */}
      {data?.insights && data.insights.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.insights.map((ins: any, idx: number) => (
            <div
              key={idx}
              onClick={() => ins.action_link && navigate(ins.action_link)}
              className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-slate-700 cursor-pointer transition-all flex items-start gap-3 shadow-sm group"
            >
              <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${
                ins.type === 'warning' ? 'bg-rose-500/10 text-rose-400' :
                ins.type === 'alert' ? 'bg-amber-500/10 text-amber-400' :
                'bg-brand-500/10 text-brand-400'
              }`}>
                <AlertCircle className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-xs text-white truncate">{ins.title}</h4>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-500 group-hover:text-white transition-colors" />
                </div>
                <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-2 leading-relaxed">{ins.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Agent Personal Performance Bar (Only for SALES_AGENT) ── */}
      {isAgent && data?.personal_workspace && (
        <div className="p-4 sm:p-5 rounded-3xl bg-slate-900 border border-brand-500/30 shadow-xl space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-brand-300 flex items-center gap-1.5">
              <Target className="w-4 h-4 text-emerald-400" />
              مستهدفي الشهري ومعدل الإنجاز الشخصي
            </span>
            <span className="text-xs text-slate-400 font-semibold">
              المعاينات: {data.personal_workspace.actual_visits} من أصل {data.personal_workspace.target_visits} مستهدفة
            </span>
          </div>

          <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
            <div
              className="bg-gradient-to-r from-brand-500 to-emerald-400 h-2.5 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, data.personal_workspace.visits_progress)}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
            <span>نسبة إنجاز المعاينات: <strong className="text-emerald-400">{data.personal_workspace.visits_progress}%</strong></span>
            <span>العملاء النشطين المخصصين لي: <strong className="text-brand-400">{data.personal_workspace.assigned_active_leads}</strong> عميل</span>
            <span>مستهدف المبيعات: <strong className="text-amber-300">{(data.personal_workspace.target_sales || 10000000).toLocaleString('ar-EG')} ج.م</strong></span>
          </div>
        </div>
      )}

      {/* ── Primary KPI Grid ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Leads */}
        <div 
          onClick={() => navigate('/leads')}
          className="p-5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all cursor-pointer shadow-lg group"
        >
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold">{isAgent ? 'عملائي المعينين' : t('total_leads')}</span>
            <div className="w-8 h-8 rounded-xl bg-brand-500/10 text-brand-400 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl sm:text-3xl font-black text-white">{summary.total_leads || 0}</div>
          <p className="text-[11px] text-slate-400 mt-1 flex items-center gap-1">
            <span className="text-emerald-400 font-bold">+{summary.new_leads || 0}</span> عملاء جدد
          </p>
        </div>

        {/* Due Today Follow-ups */}
        <div 
          onClick={() => navigate('/followups')}
          className="p-5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all cursor-pointer shadow-lg group"
        >
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold">{t('due_today')}</span>
            <div className="w-8 h-8 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl sm:text-3xl font-black text-indigo-400">{summary.due_today_followups || 0}</div>
          <p className="text-[11px] text-slate-400 mt-1">مكالمات ومتابعات اليوم</p>
        </div>

        {/* Overdue Follow-ups (Alert status) */}
        <div 
          onClick={() => navigate('/followups')}
          className={`p-5 rounded-2xl border transition-all cursor-pointer shadow-lg group ${
            summary.overdue_followups > 0 
              ? 'bg-rose-500/5 border-rose-500/30 hover:border-rose-500/50' 
              : 'bg-slate-900 border-slate-800'
          }`}
        >
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold text-rose-400">{t('overdue_tasks')}</span>
            <div className="w-8 h-8 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center group-hover:scale-110 transition-transform">
              <AlertCircle className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl sm:text-3xl font-black text-rose-400">{summary.overdue_followups || 0}</div>
          <p className="text-[11px] text-rose-300 mt-1">متابعات تتطلب اتصال فوري</p>
        </div>

        {/* Won Deals & Conversion */}
        <div 
          onClick={() => navigate('/pipeline')}
          className="p-5 rounded-2xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition-all cursor-pointer shadow-lg group"
        >
          <div className="flex items-center justify-between text-slate-400 mb-3">
            <span className="text-xs font-semibold">{t('won_deals')}</span>
            <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center group-hover:scale-110 transition-transform">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl sm:text-3xl font-black text-emerald-400">{summary.won_deals || 0}</div>
          <p className="text-[11px] text-slate-400 mt-1">
            نسبة التحويل: <span className="font-bold text-white">{summary.conversion_rate}%</span>
          </p>
        </div>
      </div>

      {/* ── Visual Analytics Grid: Sales Pipeline Funnel & Sources ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pipeline Distribution Funnel Chart */}
        <div className="lg:col-span-2 p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-bold text-sm text-white">توزيع مراحل المبيعات (Sales Funnel)</h3>
              <p className="text-xs text-slate-400">عدد العملاء في كل مرحلة من مراحل الشراء</p>
            </div>
            <button
              onClick={() => navigate('/pipeline')}
              className="text-xs text-brand-400 hover:underline flex items-center gap-1"
            >
              عرض الـ Kanban
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.pipeline_funnel || []} margin={{ top: 10, right: 10, left: -20, bottom: 25 }}>
                <XAxis 
                  dataKey="stage" 
                  tick={{ fill: '#94a3b8', fontSize: 10 }} 
                  angle={-25} 
                  textAnchor="end"
                  interval={0}
                />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
                />
                <Bar dataKey="count" fill="#0e8ce4" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Lead Sources Breakdown */}
        <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl flex flex-col">
          <h3 className="font-bold text-sm text-white mb-1">مصادر العملاء (Lead Sources)</h3>
          <p className="text-xs text-slate-400 mb-4">القنوات الأكثر توليداً للعملاء المحتملين</p>

          <div className="h-52 w-full flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data?.leads_by_source || []}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="count"
                  nameKey="source"
                >
                  {(data?.leads_by_source || []).map((entry: any, index: number) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Sources legend */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800 text-[11px]">
            {(data?.leads_by_source || []).map((s: any, idx: number) => (
              <span key={idx} className="flex items-center gap-1.5 text-slate-300">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }}></span>
                {s.source}: <strong className="text-white">{s.count}</strong>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* ── AI & Voice Health KPI Card (for Manager & Admin) ── */}
      {isManager && data?.voice_kpi && (
        <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <Volume2 className="w-5 h-5 text-brand-400" />
              <h3 className="font-bold text-sm text-white">كفاءة محرك الصوت والذكاء الاصطناعي (Voice AI Telemetry)</h3>
            </div>
            <button
              onClick={() => navigate('/ai-assistant')}
              className="text-xs text-brand-400 hover:underline flex items-center gap-1"
            >
              عرض التقرير المفصل
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-2xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-400 block text-[10px]">نجاح تحويل الصوت لنص (STT):</span>
              <span className="text-base font-bold text-emerald-400">{data.voice_kpi.stt.success_rate}%</span>
              <span className="block text-[10px] text-slate-500 mt-0.5">متوسط الاستجابة: {data.voice_kpi.stt.avg_latency_ms}ms</span>
            </div>
            <div className="p-3 rounded-2xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-400 block text-[10px]">استجابة المحادثة (LLM):</span>
              <span className="text-base font-bold text-brand-400">{data.voice_kpi.llm.success_rate}%</span>
              <span className="block text-[10px] text-slate-500 mt-0.5">متوسط التأخير: {data.voice_kpi.llm.avg_latency_ms}ms</span>
            </div>
            <div className="p-3 rounded-2xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-400 block text-[10px]">نطق الرد الصوتي (TTS):</span>
              <span className="text-base font-bold text-indigo-400">{data.voice_kpi.tts.success_rate}%</span>
              <span className="block text-[10px] text-slate-500 mt-0.5">متوسط التوليد: {data.voice_kpi.tts.avg_latency_ms}ms</span>
            </div>
            <div className="p-3 rounded-2xl bg-slate-950/60 border border-slate-800">
              <span className="text-slate-400 block text-[10px]">إجمالي الجلسات الصوتية:</span>
              <span className="text-base font-bold text-amber-300">{data.voice_kpi.total_turns}</span>
              <span className="block text-[10px] text-slate-500 mt-0.5">المقاطعات الصوتية: {data.voice_kpi.e2e.interrupted_count}</span>
            </div>
          </div>
        </div>
      )}

      {/* ── Leaderboard for Managers and Leaders ── */}
      {isManager && data?.agent_leaderboard?.length > 0 && (
        <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Award className="w-5 h-5 text-amber-400" />
              <h3 className="font-bold text-sm text-white">لوحة تميز فريق المبيعات (Leaderboard)</h3>
            </div>
            <button
              onClick={() => navigate('/agents')}
              className="text-xs text-brand-400 hover:underline flex items-center gap-1"
            >
              إدارة المستشارين والوكلاء
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs text-start">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-3 font-semibold">المستشار العقاري</th>
                  <th className="pb-3 font-semibold text-center">الفريق</th>
                  <th className="pb-3 font-semibold text-center">العملاء النشطين</th>
                  <th className="pb-3 font-semibold text-center">المعاينات المنفذة</th>
                  <th className="pb-3 font-semibold text-center">نسبة التحويل</th>
                  <th className="pb-3 font-semibold text-center">الصفقات المغلقة</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {data.agent_leaderboard.map((ag: any, idx: number) => (
                  <tr key={ag.agent_id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 font-semibold text-slate-100 flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-slate-400 font-bold">
                        {idx + 1}
                      </span>
                      {ag.agent_name}
                    </td>
                    <td className="py-3 text-center text-slate-400">{ag.team_name}</td>
                    <td className="py-3 text-center text-slate-300">{ag.leads_count}</td>
                    <td className="py-3 text-center text-slate-300">{ag.visits_count}</td>
                    <td className="py-3 text-center text-emerald-400 font-bold">{ag.conversion_rate}%</td>
                    <td className="py-3 text-center">
                      <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-bold">
                        {ag.won_deals} صفقات
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
