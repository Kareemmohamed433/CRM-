import React, { useState } from 'react';
import { Building, Lock, Mail, ArrowRight, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import { useNavigate } from 'react-router-dom';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('agent1@nexora.com');
  const [password, setPassword] = useState('Password123!');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, isRtl } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await api.post<any>('/auth/login-json', { email, password });
      login(res.access_token, res.refresh_token, res.user);
      navigate('/');
    } catch (err: any) {
      setError(err.message || 'بيانات الدخول غير صحيحة');
    } finally {
      setLoading(false);
    }
  };

  const quickSwitch = (newEmail: string) => {
    setEmail(newEmail);
    setPassword('Password123!');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background ambient lighting */}
      <div className="absolute -top-40 -right-40 w-96 h-96 bg-brand-600/20 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-600/20 rounded-full blur-3xl pointer-events-none"></div>

      <div className="max-w-md w-full bg-slate-900/90 border border-slate-800 rounded-3xl p-8 shadow-2xl relative z-10 backdrop-blur-xl">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-500 mx-auto flex items-center justify-center text-white shadow-xl shadow-brand-500/20 mb-3">
            <Building className="w-7 h-7" />
          </div>
          <h1 className="text-2xl font-black tracking-tight text-white">Nexora Real Estate CRM</h1>
          <p className="text-xs text-slate-400 mt-1">منصة إدارة مبيعات العقارات الذكية متعددة الشركات</p>
        </div>

        {error && (
          <div className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs text-center font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4 text-start">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">البريد الإلكتروني</label>
            <div className="relative">
              <Mail className="w-4 h-4 text-slate-500 absolute top-3.5 start-3.5" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-slate-800/80 border border-slate-700 rounded-xl py-2.5 ps-10 pe-4 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500"
                placeholder="name@company.com"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">كلمة المرور</label>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute top-3.5 start-3.5" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-800/80 border border-slate-700 rounded-xl py-2.5 ps-10 pe-4 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-3 px-4 rounded-xl font-bold text-sm bg-gradient-to-r from-brand-600 to-indigo-600 text-white hover:from-brand-500 hover:to-indigo-500 transition-all shadow-lg shadow-brand-600/30 flex items-center justify-center gap-2"
          >
            {loading ? 'جاري التحقق...' : 'تسجيل الدخول إلى النظام'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        {/* Development Quick Role Switcher */}
        <div className="mt-8 pt-6 border-t border-slate-800">
          <p className="text-[11px] font-bold text-slate-400 mb-2 flex items-center gap-1.5 justify-center">
            <ShieldCheck className="w-3.5 h-3.5 text-brand-400" />
            تبديل الحسابات التجريبية (Development Accounts):
          </p>
          <div className="grid grid-cols-2 gap-1.5 text-[11px]">
            <button
              onClick={() => quickSwitch('agent1@nexora.com')}
              className={`p-1.5 rounded-lg border text-center transition-all ${
                email === 'agent1@nexora.com' ? 'border-brand-500 bg-brand-500/20 text-brand-300 font-bold' : 'border-slate-800 bg-slate-800/40 text-slate-400 hover:text-white'
              }`}
            >
              مستشار مبيعات (Agent 1)
            </button>
            <button
              onClick={() => quickSwitch('leader@nexora.com')}
              className={`p-1.5 rounded-lg border text-center transition-all ${
                email === 'leader@nexora.com' ? 'border-brand-500 bg-brand-500/20 text-brand-300 font-bold' : 'border-slate-800 bg-slate-800/40 text-slate-400 hover:text-white'
              }`}
            >
              قائد فريق (Team Leader)
            </button>
            <button
              onClick={() => quickSwitch('manager@nexora.com')}
              className={`p-1.5 rounded-lg border text-center transition-all ${
                email === 'manager@nexora.com' ? 'border-brand-500 bg-brand-500/20 text-brand-300 font-bold' : 'border-slate-800 bg-slate-800/40 text-slate-400 hover:text-white'
              }`}
            >
              مدير مبيعات (Sales Manager)
            </button>
            <button
              onClick={() => quickSwitch('admin@nexora.com')}
              className={`p-1.5 rounded-lg border text-center transition-all ${
                email === 'admin@nexora.com' ? 'border-brand-500 bg-brand-500/20 text-brand-300 font-bold' : 'border-slate-800 bg-slate-800/40 text-slate-400 hover:text-white'
              }`}
            >
              مدير الشركة (Company Admin)
            </button>
            <button
              onClick={() => quickSwitch('superadmin@nexora.com')}
              className={`p-1.5 rounded-lg border text-center transition-all ${
                email === 'superadmin@nexora.com' ? 'border-brand-500 bg-brand-500/20 text-brand-300 font-bold' : 'border-slate-800 bg-slate-800/40 text-slate-400 hover:text-white'
              }`}
            >
              Super Admin
            </button>
            <button
              onClick={() => quickSwitch('agent@horizon.com')}
              className={`p-1.5 rounded-lg border text-center transition-all ${
                email === 'agent@horizon.com' ? 'border-amber-500 bg-amber-500/20 text-amber-300 font-bold' : 'border-slate-800 bg-slate-800/40 text-amber-400 hover:text-white'
              }`}
              title="شركة هورايزن المستقلة لاختبار عزل المستأجرين"
            >
              شركة أخرى (Horizon Tenant)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
