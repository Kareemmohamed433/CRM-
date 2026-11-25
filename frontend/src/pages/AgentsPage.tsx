import React, { useState, useEffect } from 'react';
import {
  Users, Bot, Settings, Volume2, Shield, ArrowRightLeft,
  CheckCircle2, Clock, Target, Phone, Mail, Award, AlertCircle,
  Sliders, UserCheck, X, RefreshCw, Sparkles, Building
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { AgentWithStats, SalesAgentProfile } from '../types';

export const AgentsPage: React.FC = () => {
  const { user } = useAuth();
  const [agents, setAgents] = useState<AgentWithStats[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Edit Profile Modal
  const [editingAgent, setEditingAgent] = useState<AgentWithStats | null>(null);
  const [profileForm, setProfileForm] = useState<Partial<SalesAgentProfile>>({});
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Transfer Leads Modal
  const [transferSourceAgent, setTransferSourceAgent] = useState<AgentWithStats | null>(null);
  const [transferTargetId, setTransferTargetId] = useState<number | ''>('');
  const [transferReason, setTransferReason] = useState('إعادة توزيع جغرافي للمشاريع');
  const [transferNotes, setTransferNotes] = useState('');
  const [isTransferring, setIsTransferring] = useState(false);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    setIsLoading(true);
    try {
      const data = await api.get<AgentWithStats[]>('/agents');
      setAgents(data);
    } catch (err) {
      console.error('Failed to load agents:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const openEditModal = (ag: AgentWithStats) => {
    setEditingAgent(ag);
    setProfileForm({
      personality_prompt: ag.profile?.personality_prompt || 'مندوب مبيعات عقاري محترف، ودود ولبق، يتحدث باللهجة المصرية الطبيعية.',
      preferred_voice: ag.profile?.preferred_voice || 'ar-EG-SalmaNeural',
      speaking_rate: ag.profile?.speaking_rate || '+20%',
      working_hours_start: ag.profile?.working_hours_start || '09:00',
      working_hours_end: ag.profile?.working_hours_end || '18:00',
      max_active_leads: ag.profile?.max_active_leads || 50,
      monthly_target_sales: ag.profile?.monthly_target_sales || 10000000,
      target_visits_per_month: ag.profile?.target_visits_per_month || 20,
      is_accepting_leads: ag.profile?.is_accepting_leads ?? true
    });
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAgent) return;

    setIsSavingProfile(true);
    try {
      await api.patch(`/agents/${editingAgent.id}/profile`, profileForm);
      setSuccessBanner(`تم تحديث إعدادات ونبرة الذكاء الاصطناعي للمستشار ${editingAgent.full_name} بنجاح`);
      setEditingAgent(null);
      loadAgents();
      setTimeout(() => setSuccessBanner(null), 4000);
    } catch (err: any) {
      alert(`فشل الحفظ: ${err.message || 'خطأ في الخادم'}`);
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleBulkTransfer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!transferSourceAgent || !transferTargetId) return;

    setIsTransferring(true);
    try {
      const res = await api.post<any>(`/agents/${transferSourceAgent.id}/transfer-leads`, {
        target_agent_id: Number(transferTargetId),
        reason: transferReason,
        notes: transferNotes
      });
      setSuccessBanner(`تم بنجاح نقل ${res.transferred_count} عميل محتمل إلى ${res.target_agent}`);
      setTransferSourceAgent(null);
      setTransferTargetId('');
      setTransferNotes('');
      loadAgents();
      setTimeout(() => setSuccessBanner(null), 4000);
    } catch (err: any) {
      alert(`فشل النقل: ${err.message || 'خطأ في العملية'}`);
    } finally {
      setIsTransferring(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* ── Top Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-4 sm:p-5 rounded-2xl shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Users className="w-5 h-5 text-brand-400" />
            فريق مستشاري المبيعات ووكلاء الذكاء الاصطناعي (Sales Agents)
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            تخصيص نبرة الصوت وشخصية كل مندوب مبيعات، متابعة مؤشرات الأداء الفردية، وإعادة توزيع المهام بين الفرق
          </p>
        </div>
      </div>

      {/* ── Success Alert ── */}
      {successBanner && (
        <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-bold flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{successBanner}</span>
        </div>
      )}

      {/* ── Agents Grid ── */}
      {isLoading ? (
        <div className="p-12 text-center text-xs text-slate-500">جاري تحميل بيانات مستشاري المبيعات...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((ag) => (
            <div
              key={ag.id}
              className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 flex flex-col justify-between space-y-4 shadow-sm hover:border-slate-700 transition-all"
            >
              {/* Agent Head */}
              <div>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-600 text-white flex items-center justify-center font-bold text-base shadow-md shadow-brand-600/20">
                      {ag.full_name.charAt(0)}
                    </div>
                    <div>
                      <h3 className="font-bold text-sm text-white">{ag.full_name}</h3>
                      <p className="text-xs text-slate-400">{ag.team_name || 'الفريق العام'} • {ag.email}</p>
                    </div>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                    ag.is_active ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                  }`}>
                    {ag.is_active ? 'نشط' : 'معطل'}
                  </span>
                </div>

                {/* AI Persona Pill */}
                <div className="p-2.5 rounded-xl bg-slate-800/60 border border-slate-700/60 mb-3 text-xs">
                  <div className="flex items-center justify-between text-brand-300 font-bold mb-1 text-[11px]">
                    <span className="flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                      الصوت والشخصية:
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-900 text-slate-300">
                      {ag.profile?.preferred_voice === 'ar-EG-SalmaNeural' ? 'سلمى (مصرية)' : 'شاكر (مصري)'} ({ag.profile?.speaking_rate || '+20%'})
                    </span>
                  </div>
                  <p className="text-slate-300 line-clamp-2 text-[11px] leading-relaxed">
                    {ag.profile?.personality_prompt || 'شخصية مبيعات احترافية متزنة.'}
                  </p>
                </div>

                {/* KPI Metrics */}
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">العملاء المعينين:</span>
                    <span className="font-bold text-brand-400">{ag.total_assigned_leads}</span>
                  </div>
                  <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">المعاينات:</span>
                    <span className="font-bold text-indigo-400">{ag.completed_visits}</span>
                  </div>
                  <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">نسبة التحويل:</span>
                    <span className="font-bold text-emerald-400">{ag.conversion_rate}%</span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-slate-800/80 flex items-center gap-2">
                <button
                  onClick={() => openEditModal(ag)}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700/60 transition-all"
                >
                  <Sliders className="w-3.5 h-3.5 text-brand-400" />
                  <span>تعديل الشخصية والصوت</span>
                </button>
                <button
                  onClick={() => setTransferSourceAgent(ag)}
                  className="p-2 rounded-xl bg-brand-600/20 hover:bg-brand-600/30 text-brand-300 border border-brand-500/30 transition-all"
                  title="نقل وإعادة توزيع العملاء"
                >
                  <ArrowRightLeft className="w-4 h-4 text-brand-400" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Edit Personality & Voice Modal ── */}
      {editingAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-5 space-y-4 shadow-2xl text-start">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <Sliders className="w-5 h-5 text-brand-400" />
                <h3 className="font-bold text-base text-white">إعدادات المندوب الذكي ({editingAgent.full_name})</h3>
              </div>
              <button onClick={() => setEditingAgent(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveProfile} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  موجه شخصية وأسلوب الذكاء الاصطناعي (Personality Prompt):
                </label>
                <textarea
                  rows={3}
                  value={profileForm.personality_prompt || ''}
                  onChange={(e) => setProfileForm({ ...profileForm, personality_prompt: e.target.value })}
                  placeholder="مثال: مندوب مبيعات عقاري ودود، يتحدث باللهجة المصرية..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">الصوت المفضل (Egyptian Voice):</label>
                  <select
                    value={profileForm.preferred_voice || 'ar-EG-SalmaNeural'}
                    onChange={(e) => setProfileForm({ ...profileForm, preferred_voice: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl py-2 px-2.5 text-slate-200 focus:outline-none focus:border-brand-500"
                  >
                    <option value="ar-EG-SalmaNeural">سلمى (أنثوي مصري طبيعي)</option>
                    <option value="ar-EG-ShakirNeural">شاكر (ذكوري مصري طبيعي)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">سرعة الإلقاء (Tempo Rate):</label>
                  <select
                    value={profileForm.speaking_rate || '+20%'}
                    onChange={(e) => setProfileForm({ ...profileForm, speaking_rate: e.target.value })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl py-2 px-2.5 text-slate-200 focus:outline-none focus:border-brand-500"
                  >
                    <option value="+10%">طبيعي هادئ (+10%)</option>
                    <option value="+20%">حيوي سريع (+20%)</option>
                    <option value="+25%">سريع جداً (+25%)</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">المستهدف الشهري (EGP Target):</label>
                  <input
                    type="number"
                    value={profileForm.monthly_target_sales || 10000000}
                    onChange={(e) => setProfileForm({ ...profileForm, monthly_target_sales: Number(e.target.value) })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl py-2 px-2.5 text-slate-100 focus:outline-none focus:border-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">المعاينات المستهدفة شهرياً:</label>
                  <input
                    type="number"
                    value={profileForm.target_visits_per_month || 20}
                    onChange={(e) => setProfileForm({ ...profileForm, target_visits_per_month: Number(e.target.value) })}
                    className="w-full bg-slate-800 border border-slate-700 rounded-xl py-2 px-2.5 text-slate-100 focus:outline-none focus:border-brand-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setEditingAgent(null)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={isSavingProfile}
                  className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-bold transition-all shadow-md shadow-brand-600/30"
                >
                  {isSavingProfile ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                  <span>حفظ الإعدادات</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Bulk Lead Reassignment Modal ── */}
      {transferSourceAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-5 space-y-4 shadow-2xl text-start">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <ArrowRightLeft className="w-5 h-5 text-amber-400" />
                <h3 className="font-bold text-base text-white">إعادة توزيع عملاء {transferSourceAgent.full_name}</h3>
              </div>
              <button onClick={() => setTransferSourceAgent(null)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleBulkTransfer} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">المستشار المستلم (Target Agent):</label>
                <select
                  required
                  value={transferTargetId}
                  onChange={(e) => setTransferTargetId(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl py-2 px-3 text-slate-200 focus:outline-none focus:border-brand-500"
                >
                  <option value="">اختر مستشار المبيعات البديل...</option>
                  {agents.filter(a => a.id !== transferSourceAgent.id).map(a => (
                    <option key={a.id} value={a.id}>{a.full_name} ({a.team_name || 'عام'})</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">سبب التحويل:</label>
                <input
                  type="text"
                  required
                  value={transferReason}
                  onChange={(e) => setTransferReason(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl py-2 px-3 text-slate-100 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">ملاحظات إضافية:</label>
                <textarea
                  rows={2}
                  value={transferNotes}
                  onChange={(e) => setTransferNotes(e.target.value)}
                  placeholder="ملاحظات توضيحية للفريق وللمستلم..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setTransferSourceAgent(null)}
                  className="px-4 py-2 rounded-xl text-slate-400 hover:text-white"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={isTransferring || !transferTargetId}
                  className="flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold transition-all shadow-md shadow-amber-600/30 disabled:opacity-50"
                >
                  {isTransferring ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                  <span>اعتماد ونقل العملاء</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

