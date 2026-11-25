import React, { useEffect, useState } from 'react';
import { 
  Settings, Building, Users, ShieldCheck, CheckCircle2, 
  ExternalLink, Plug, AlertCircle, RefreshCw, Key 
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';

export const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const [teams, setTeams] = useState<any[]>([]);
  const [companyUsers, setCompanyUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get<any[]>('/teams'),
      api.get<any[]>('/users')
    ])
      .then(([tms, usrs]) => {
        setTeams(tms);
        setCompanyUsers(usrs);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const integrations = [
    {
      name: 'WhatsApp Business Cloud Platform',
      category: 'Messaging & Follow-ups',
      status: 'Connected (Development Mock)',
      description: 'إرسال إشعارات ومتابعات للعملاء عبر رقم الأعمال المعتمد',
      active: true,
    },
    {
      name: 'Meta Ads Webhook (Facebook / Instagram)',
      category: 'Lead Capture',
      status: 'Active (Real-time Lead Ingestion)',
      description: 'التقاط العملاء المحتملين تلقائياً وتوزيعهم على فرق المبيعات',
      active: true,
    },
    {
      name: 'Arabic Speech-to-Text & NLP Engine',
      category: 'Voice AI',
      status: 'Active (Local Offline Provider)',
      description: 'تحليل اللهجة المصرية والعربية الفصحى لملء استمارات المعاينة',
      active: true,
    },
    {
      name: 'LLM Reasoning & CRM Tool Orchestrator',
      category: 'AI Assistant',
      status: 'Active (Deterministic RBAC Guardrails)',
      description: 'تنفيذ الأدوات المصرحة واستخراج ملخصات المعاينات وحساب الأولويات',
      active: true,
    }
  ];

  return (
    <div className="space-y-6 text-start">
      {/* Header */}
      <div>
        <h2 className="text-xl sm:text-2xl font-black text-white flex items-center gap-2">
          <Settings className="w-6 h-6 text-brand-400" />
          <span>إعدادات الشركة والربط الخارجي (Company Settings & Integrations)</span>
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          بيانات المستأجر المعزولة، إدارة الفرق، وحالة الربط بالقنوات الرسمية
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Tenant & Teams */}
        <div className="space-y-6">
          {/* Company Profile */}
          <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
            <h3 className="font-bold text-sm text-white flex items-center gap-2">
              <Building className="w-4 h-4 text-brand-400" />
              بيانات المستأجر (Tenant Profile)
            </h3>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">اسم الشركة:</span>
                <span className="font-bold text-white">{user?.company_name || 'Nexora Developments'}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">معرف المستأجر (Company ID):</span>
                <span className="font-mono text-brand-400">{user?.company_id}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">العملة الأساسية:</span>
                <span className="font-semibold text-slate-200">الجنيه المصري (EGP)</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800/60">
                <span className="text-slate-400">عزل البيانات:</span>
                <span className="font-bold text-emerald-400 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  محمي بنسبة 100%
                </span>
              </div>
            </div>
          </div>

          {/* Teams List */}
          <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl space-y-3">
            <h3 className="font-bold text-sm text-white flex items-center gap-2">
              <Users className="w-4 h-4 text-indigo-400" />
              فرق المبيعات التابعة (Sales Teams)
            </h3>

            <div className="space-y-2 text-xs">
              {teams.length === 0 ? (
                <p className="text-slate-500 py-3 text-center">لا توجد فرق مسجلة</p>
              ) : (
                teams.map((t) => (
                  <div key={t.id} className="p-3 rounded-xl bg-slate-800/50 border border-slate-800 flex justify-between items-center">
                    <div>
                      <span className="font-bold text-slate-200 block">{t.name}</span>
                      <span className="text-[10px] text-slate-400">القائد: {t.leader_name || 'غير محدد'}</span>
                    </div>
                    <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-300 font-bold">
                      {t.member_count} أعضاء
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Official Integrations Status */}
        <div className="lg:col-span-2 p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <h3 className="font-bold text-sm text-white flex items-center gap-2">
                <Plug className="w-4 h-4 text-emerald-400" />
                حالة الربط والخدمات الخارجية (External Integrations)
              </h3>
              <p className="text-xs text-slate-400">
                بيان القنوات المتصلة والمحولات الآمنة للاستخدام المحلي والإنتاجي
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {integrations.map((item, idx) => (
              <div
                key={idx}
                className="p-4 rounded-2xl bg-slate-800/40 border border-slate-800 space-y-2.5 flex flex-col justify-between text-xs"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold text-brand-400 uppercase tracking-wider">{item.category}</span>
                    <span className="flex items-center gap-1 text-[10px] font-bold text-emerald-400">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                      متصل
                    </span>
                  </div>
                  <h4 className="font-bold text-slate-100 mt-1">{item.name}</h4>
                  <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">{item.description}</p>
                </div>

                <div className="pt-2 border-t border-slate-800/80 text-[10px] text-slate-400 flex items-center justify-between">
                  <span>الحالة: {item.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
