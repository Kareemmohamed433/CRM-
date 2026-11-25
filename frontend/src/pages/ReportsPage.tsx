import React, { useEffect, useState } from 'react';
import { 
  BarChart3, TrendingUp, Users, PieChart as PieIcon, 
  AlertCircle, ArrowUpRight, ShieldCheck 
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell } from 'recharts';
import { api } from '../api/client';

const COLORS = ['#0e8ce4', '#6366f1', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6'];

export const ReportsPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get<any>('/reports/overview')
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="py-24 text-center text-slate-400 text-xs animate-pulse">
        جاري تجميع وحساب تقارير المبيعات ونسب التحويل...
      </div>
    );
  }

  const conversions = data?.conversions || {};

  return (
    <div className="space-y-6 text-start">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-brand-400" />
            <span>التقارير وتحليلات التحويل (Reports & Analytics)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            رصد معدلات تحويل المعاينات لصفقات بيع وأسباب رفض العملاء الموثقة
          </p>
        </div>
      </div>

      {/* Conversion Rate Highlight Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl">
          <span className="text-xs text-slate-400 block mb-1">إجمالي العملاء المسجلين</span>
          <div className="text-3xl font-black text-white">{conversions.total_leads || 0}</div>
          <p className="text-[11px] text-brand-400 mt-1">قاعدة العملاء النشطة بالشركة</p>
        </div>

        <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl">
          <span className="text-xs text-slate-400 block mb-1">معدل تحويل المعاينات (Lead to Visit)</span>
          <div className="text-3xl font-black text-brand-400">{conversions.lead_to_visit_rate || 0}%</div>
          <p className="text-[11px] text-slate-400 mt-1">{conversions.visited_leads || 0} عملاء أتموا معاينة موقع</p>
        </div>

        <div className="p-5 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl">
          <span className="text-xs text-slate-400 block mb-1">معدل إغلاق الصفقات (Visit to Deal)</span>
          <div className="text-3xl font-black text-emerald-400">{conversions.visit_to_won_rate || 0}%</div>
          <p className="text-[11px] text-emerald-300 mt-1">{conversions.won_leads || 0} صفقات ناجحة مغلقة</p>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pipeline Conversion Funnel */}
        <div className="p-6 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl">
          <h3 className="font-bold text-sm text-white mb-1">قمع المبيعات ومراحل التحويل</h3>
          <p className="text-xs text-slate-400 mb-4">انتقال العملاء عبر المراحل من الاستلام حتى الإغلاق</p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.funnel || []} margin={{ top: 10, right: 10, left: -20, bottom: 25 }}>
                <XAxis dataKey="stage" tick={{ fill: '#94a3b8', fontSize: 10 }} angle={-25} textAnchor="end" interval={0} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '12px', fontSize: '12px' }} />
                <Bar dataKey="count" fill="#6366f1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Customer Objections Breakdown */}
        <div className="p-6 rounded-3xl bg-slate-900 border border-slate-800 shadow-xl">
          <h3 className="font-bold text-sm text-white mb-1">تحليل أسباب الاعتراض ورفض الوحدات</h3>
          <p className="text-xs text-slate-400 mb-4">الأسباب الأكثر تكراراً التي سجلها المستشارون بعد المعاينات</p>
          <div className="space-y-3">
            {(!data?.objections || data.objections.length === 0) ? (
              <p className="text-xs text-slate-500 py-10 text-center">لا توجد اعتراضات مسجلة بعد</p>
            ) : (
              data.objections.map((obj: any, idx: number) => (
                <div key={idx} className="p-3 rounded-2xl bg-slate-800/50 border border-slate-800 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-400" />
                    <span className="font-bold text-slate-200">{obj.reason}</span>
                  </div>
                  <span className="px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 font-bold">
                    {obj.count} مرات
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
