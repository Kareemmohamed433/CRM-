import React, { useState, useEffect } from 'react';
import {
  Sparkles, Megaphone, Share2, Calendar, Clock, CheckCircle2,
  AlertTriangle, RefreshCw, Eye, Edit3, Trash2, Send, ExternalLink,
  Settings as SettingsIcon, ShieldCheck, FileText, Check, X,
  Globe, ChevronRight, Layers, Sliders, PlayCircle
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import {
  MarketingPost, MarketingSetting, MarketingDashboardStats,
  MarketingLog, MarketingPublishingStatus, FacebookConnectionTestResponse
} from '../types';

export const MarketingStudioPage: React.FC = () => {
  const { user, isRtl } = useAuth();

  // State
  const [stats, setStats] = useState<MarketingDashboardStats | null>(null);
  const [posts, setPosts] = useState<MarketingPost[]>([]);
  const [settings, setSettings] = useState<MarketingSetting | null>(null);
  const [logs, setLogs] = useState<MarketingLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('ALL');

  // Modals state
  const [previewPost, setPreviewPost] = useState<MarketingPost | null>(null);
  const [editingPost, setEditingPost] = useState<MarketingPost | null>(null);
  const [editHeadline, setEditHeadline] = useState('');
  const [editCaption, setEditCaption] = useState('');
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);

  // Settings form state
  const [formPageId, setFormPageId] = useState('');
  const [formAccessToken, setFormAccessToken] = useState('');
  const [formAutoGen, setFormAutoGen] = useState(true);
  const [formAutoPub, setFormAutoPub] = useState(false);
  const [formGenTime, setFormGenTime] = useState('19:00');
  const [formPubTime, setFormPubTime] = useState('20:00');
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState<FacebookConnectionTestResponse | null>(null);
  const [savingSettings, setSavingSettings] = useState(false);

  useEffect(() => {
    loadAllData();
  }, [filterStatus]);

  const loadAllData = async () => {
    try {
      setLoading(true);
      const [statsRes, postsRes, settingsRes] = await Promise.all([
        api.get<MarketingDashboardStats>('/marketing/stats'),
        api.get<MarketingPost[]>(`/marketing/posts${filterStatus !== 'ALL' ? `?status_filter=${filterStatus}` : ''}`),
        api.get<MarketingSetting>('/marketing/settings')
      ]);

      setStats(statsRes);
      setPosts(postsRes);
      setSettings(settingsRes);

      // Initialize settings form
      setFormPageId(settingsRes.facebook_page_id || '');
      setFormAutoGen(settingsRes.auto_generation_enabled);
      setFormAutoPub(settingsRes.auto_publishing_enabled);
      setFormGenTime(settingsRes.generation_time || '19:00');
      setFormPubTime(settingsRes.publishing_time || '20:00');
    } catch (err) {
      console.error('Failed to load marketing studio data', err);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateToday = async (force: boolean = false) => {
    try {
      setGenerating(true);
      await api.post('/marketing/posts/generate', { force });
      await loadAllData();
    } catch (err: any) {
      alert(err.message || 'فشل توليد منشور اليوم.');
    } finally {
      setGenerating(false);
    }
  };

  const handleRegenerateImage = async (post: MarketingPost) => {
    if (!window.confirm('هل تريد إعادة توليد صورة جديدة وتطبيق هوية NEXORA؟')) return;
    try {
      setActionLoadingId(post.id);
      await api.post(`/marketing/posts/${post.id}/regenerate-image`, {});
      await loadAllData();
    } catch (err: any) {
      alert(err.message || 'فشل إعادة توليد الصورة.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleApprove = async (post: MarketingPost) => {
    try {
      setActionLoadingId(post.id);
      await api.post(`/marketing/posts/${post.id}/approve`, {});
      await loadAllData();
    } catch (err: any) {
      alert(err.message || 'فشل اعتماد المنشور.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handlePublishNow = async (post: MarketingPost) => {
    if (!window.confirm('هل أنت متأكد من رغبتك في نشر هذا المنشور فوراً على صفحة فيسبوك المتصلة؟')) return;
    try {
      setActionLoadingId(post.id);
      await api.post(`/marketing/posts/${post.id}/publish-now`, {});
      alert('تم النشر بنجاح على صفحة فيسبوك!');
      await loadAllData();
    } catch (err: any) {
      alert(err.message || 'فشل النشر على فيسبوك.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDeletePost = async (post: MarketingPost) => {
    if (!window.confirm('هل تريد حذف هذه المسودة نهائياً؟')) return;
    try {
      setActionLoadingId(post.id);
      await api.delete(`/marketing/posts/${post.id}`);
      await loadAllData();
    } catch (err: any) {
      alert(err.message || 'فشل حذف المنشور.');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingPost) return;
    try {
      await api.put(`/marketing/posts/${editingPost.id}`, {
        headline: editHeadline,
        caption: editCaption
      });
      setEditingPost(null);
      await loadAllData();
    } catch (err: any) {
      alert(err.message || 'فشل حفظ التعديلات.');
    }
  };

  const handleTestConnection = async () => {
    try {
      setTestingConnection(true);
      setTestResult(null);
      const res = await api.post<FacebookConnectionTestResponse>('/marketing/facebook/test-connection', {
        page_id: formPageId,
        page_access_token: formAccessToken || undefined
      });
      setTestResult(res);
      if (res.connected) {
        await loadAllData();
      }
    } catch (err: any) {
      setTestResult({
        connected: false,
        message: err.message || 'تعذر الاتصال بـ Meta Graph API.',
        permissions: []
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleSaveSettings = async () => {
    try {
      setSavingSettings(true);
      await api.put('/marketing/settings', {
        facebook_page_id: formPageId,
        facebook_access_token: formAccessToken || undefined,
        auto_generation_enabled: formAutoGen,
        auto_publishing_enabled: formAutoPub,
        generation_time: formGenTime,
        publishing_time: formPubTime
      });
      setShowSettingsModal(false);
      alert('تم حفظ الإعدادات بنجاح.');
      await loadAllData();
    } catch (err: any) {
      alert(err.message || 'فشل حفظ الإعدادات.');
    } finally {
      setSavingSettings(false);
    }
  };

  const handleOpenLogs = async () => {
    try {
      setShowLogsModal(true);
      const logsRes = await api.get<MarketingLog[]>('/marketing/logs?limit=30');
      setLogs(logsRes);
    } catch (err) {
      console.error(err);
    }
  };

  const getStatusBadge = (status: MarketingPublishingStatus) => {
    switch (status) {
      case 'PUBLISHED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3.5 h-3.5" />
            منشور على فيسبوك
          </span>
        );
      case 'SCHEDULED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Clock className="w-3.5 h-3.5" />
            مجدول للنشر التلقائي
          </span>
        );
      case 'DRAFT':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Edit3 className="w-3.5 h-3.5" />
            مسودة بانتظار الاعتماد
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <AlertTriangle className="w-3.5 h-3.5" />
            فشل النشر
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6 text-start">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-slate-800 rounded-3xl p-6 lg:p-8 shadow-xl relative overflow-hidden">
        <div className="absolute -top-24 -left-24 w-80 h-80 bg-brand-500/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-80 h-80 bg-indigo-500/15 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 via-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-brand-500/20">
                <Megaphone className="w-6 h-6" />
              </div>
              <div>
                <h1 className="text-2xl lg:text-3xl font-black text-white tracking-tight flex items-center gap-2">
                  AI Marketing Studio
                  <span className="text-xs font-bold uppercase tracking-widest px-2.5 py-0.5 rounded-full bg-brand-500/20 text-brand-300 border border-brand-500/30">
                    Auto-Publish
                  </span>
                </h1>
                <p className="text-sm text-slate-400 mt-0.5">
                  توليد ونشر منشور تسويقي يومي بالذكاء الاصطناعي مع الحفاظ التام على هوية NEXORA
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => handleGenerateToday(false)}
              disabled={generating}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-semibold text-sm shadow-lg shadow-brand-600/20 disabled:opacity-50 transition-all cursor-pointer"
            >
              {generating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  جاري التوليد والتصميم...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-cyan-300" />
                  توليد منشور اليوم
                </>
              )}
            </button>

            <button
              onClick={() => setShowSettingsModal(true)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-slate-700/80 text-sm font-semibold transition-all cursor-pointer"
            >
              <SettingsIcon className="w-4 h-4 text-slate-400" />
              إعدادات النشر والربط
            </button>

            <button
              onClick={handleOpenLogs}
              className="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-slate-800/60 hover:bg-slate-800 text-slate-300 border border-slate-700/60 text-sm font-medium transition-all cursor-pointer"
              title="سجل العمليات"
            >
              <FileText className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* KPI Overview Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-slate-400">إجمالي المنشورات</span>
          <p className="text-2xl font-bold text-white mt-1">{stats?.total_posts ?? 0}</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-emerald-400">نُشر على فيسبوك</span>
          <p className="text-2xl font-bold text-emerald-400 mt-1">{stats?.published_posts ?? 0}</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-indigo-400">مجدول للنشر</span>
          <p className="text-2xl font-bold text-indigo-400 mt-1">{stats?.scheduled_posts ?? 0}</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-amber-400">مسودات معلقة</span>
          <p className="text-2xl font-bold text-amber-400 mt-1">{stats?.draft_posts ?? 0}</p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-slate-400">التوليد اليومي</span>
          <div className="flex items-center gap-1.5 mt-2">
            <div className={`w-2 h-2 rounded-full ${stats?.auto_generation_enabled ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
            <span className="text-xs font-bold text-slate-300">
              {stats?.auto_generation_enabled ? '7:00 م (مفعل)' : 'معطل'}
            </span>
          </div>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-sm">
          <span className="text-xs font-semibold text-slate-400">ربط صفحة فيسبوك</span>
          <div className="flex items-center gap-1.5 mt-2">
            <div className={`w-2 h-2 rounded-full ${stats?.facebook_connected ? 'bg-emerald-400' : 'bg-rose-500'}`} />
            <span className="text-xs font-bold text-slate-300 truncate">
              {stats?.facebook_connected ? (stats?.facebook_page_name || 'متصل') : 'غير متصل'}
            </span>
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {[
            { id: 'ALL', label: 'كافة المنشورات' },
            { id: 'PUBLISHED', label: 'تم النشر' },
            { id: 'SCHEDULED', label: 'مجدول' },
            { id: 'DRAFT', label: 'مسودات' },
            { id: 'FAILED', label: 'فشل التوليد' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setFilterStatus(tab.id)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer whitespace-nowrap ${
                filterStatus === tab.id
                  ? 'bg-brand-600 text-white shadow-sm shadow-brand-500/20'
                  : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <span className="text-xs text-slate-500 hidden sm:inline">
          عرض {posts.length} منشور
        </span>
      </div>

      {/* Posts Cards Grid */}
      {loading ? (
        <div className="py-20 text-center">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-brand-500 mb-3" />
          <p className="text-sm text-slate-400">جاري تحميل المحفظة التسويقية...</p>
        </div>
      ) : posts.length === 0 ? (
        <div className="bg-slate-900/60 border border-slate-800 rounded-3xl p-12 text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
            <Megaphone className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">لا توجد منشورات حتى الآن</h3>
            <p className="text-sm text-slate-400 mt-1 max-w-md mx-auto">
              اضغط على "توليد منشور اليوم" لتوليد فكرة تسويقية جديدة وكتابة المحتوى وتصميم بوستر احترافي بهوية NEXORA.
            </p>
          </div>
          <button
            onClick={() => handleGenerateToday(false)}
            disabled={generating}
            className="px-6 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold text-sm shadow-lg shadow-brand-600/20 transition-all cursor-pointer inline-flex items-center gap-2"
          >
            <Sparkles className="w-4 h-4 text-cyan-300" />
            توليد أول منشور الآن
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {posts.map(post => (
            <div
              key={post.id}
              className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 rounded-3xl overflow-hidden shadow-lg transition-all flex flex-col group"
            >
              {/* Image Preview Container */}
              <div className="relative aspect-[4/5] bg-slate-950 overflow-hidden border-b border-slate-800">
                {post.image_path ? (
                  <img
                    src={post.image_path}
                    alt={post.headline}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                ) : (
                  <div className="w-full h-full flex flex-col items-center justify-center text-slate-600 p-6 text-center">
                    <RefreshCw className="w-8 h-8 animate-spin mb-2 text-brand-500" />
                    <span className="text-xs">جاري تجهيز الصورة...</span>
                  </div>
                )}

                {/* Floating Top Badges */}
                <div className="absolute top-3 inset-x-3 flex items-center justify-between gap-2 pointer-events-none">
                  {getStatusBadge(post.publishing_status)}
                  <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-slate-900/85 backdrop-blur-md text-slate-300 border border-slate-700">
                    {post.post_date}
                  </span>
                </div>

                {/* Quick Hover Action Overlay */}
                <div className="absolute inset-0 bg-slate-950/60 opacity-0 group-hover:opacity-100 backdrop-blur-xs transition-opacity flex items-center justify-center gap-3">
                  <button
                    onClick={() => setPreviewPost(post)}
                    className="p-3 rounded-full bg-slate-900/90 text-white hover:bg-brand-600 transition-colors shadow-xl cursor-pointer"
                    title="معاينة المنشور"
                  >
                    <Eye className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => {
                      setEditingPost(post);
                      setEditHeadline(post.headline);
                      setEditCaption(post.caption);
                    }}
                    className="p-3 rounded-full bg-slate-900/90 text-white hover:bg-amber-600 transition-colors shadow-xl cursor-pointer"
                    title="تعديل النص"
                  >
                    <Edit3 className="w-5 h-5" />
                  </button>
                  {post.publishing_status !== 'PUBLISHED' && (
                    <button
                      onClick={() => handleRegenerateImage(post)}
                      disabled={actionLoadingId === post.id}
                      className="p-3 rounded-full bg-slate-900/90 text-white hover:bg-indigo-600 transition-colors shadow-xl cursor-pointer"
                      title="إعادة توليد الصورة"
                    >
                      <RefreshCw className={`w-5 h-5 ${actionLoadingId === post.id ? 'animate-spin' : ''}`} />
                    </button>
                  )}
                </div>
              </div>

              {/* Card Details */}
              <div className="p-5 flex-1 flex flex-col justify-between space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-bold px-2 py-0.5 rounded-md bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 truncate">
                      {post.topic}
                    </span>
                  </div>

                  <h3 className="font-bold text-base text-white line-clamp-2 leading-snug">
                    {post.headline}
                  </h3>

                  <p className="text-xs text-slate-400 line-clamp-3 leading-relaxed whitespace-pre-line">
                    {post.caption}
                  </p>

                  {post.error_message && (
                    <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span className="truncate">{post.error_message}</span>
                    </div>
                  )}

                  {post.facebook_post_id && (
                    <div className="flex items-center gap-1.5 text-xs text-brand-400 pt-1">
                      <Share2 className="w-3.5 h-3.5" />
                      <span>معرف فيسبوك: {post.facebook_post_id}</span>
                      {post.facebook_permalink_url && (
                        <a
                          href={post.facebook_permalink_url}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:text-brand-300 inline-flex items-center gap-0.5 ms-auto"
                        >
                          <ExternalLink className="w-3 h-3" />
                          عرض على فيسبوك
                        </a>
                      )}
                    </div>
                  )}
                </div>

                {/* Card Action Footer */}
                <div className="border-t border-slate-800/80 pt-3 flex items-center justify-between gap-2">
                  <button
                    onClick={() => setPreviewPost(post)}
                    className="text-xs font-semibold text-slate-300 hover:text-white flex items-center gap-1.5 cursor-pointer"
                  >
                    <Eye className="w-3.5 h-3.5 text-slate-400" />
                    معاينة كاملة
                  </button>

                  <div className="flex items-center gap-2">
                    {post.publishing_status === 'DRAFT' && (
                      <button
                        onClick={() => handleApprove(post)}
                        disabled={actionLoadingId === post.id}
                        className="px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/30 text-xs font-semibold transition-all cursor-pointer flex items-center gap-1"
                      >
                        <Check className="w-3.5 h-3.5" />
                        اعتماد
                      </button>
                    )}

                    {post.publishing_status !== 'PUBLISHED' && (
                      <button
                        onClick={() => handlePublishNow(post)}
                        disabled={actionLoadingId === post.id}
                        className="px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold transition-all cursor-pointer flex items-center gap-1 shadow-sm shadow-brand-500/20"
                      >
                        <Send className="w-3.5 h-3.5" />
                        نشر الآن
                      </button>
                    )}

                    {post.publishing_status !== 'PUBLISHED' && (
                      <button
                        onClick={() => handleDeletePost(post)}
                        disabled={actionLoadingId === post.id}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                        title="حذف"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 1. Facebook Post Simulation Preview Modal */}
      {/* ------------------------------------------------------------- */}
      {previewPost && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <span className="text-sm font-bold text-white flex items-center gap-2">
                <Megaphone className="w-4 h-4 text-brand-400" />
                معاينة منشور فيسبوك (Facebook Feed Preview)
              </span>
              <button
                onClick={() => setPreviewPost(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Simulated Facebook Feed Post Card */}
            <div className="p-4">
              <div className="bg-[#18191a] text-slate-100 rounded-2xl border border-slate-800 shadow-xl overflow-hidden font-sans">
                {/* FB Post Header */}
                <div className="p-3.5 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-brand-600 to-indigo-600 flex items-center justify-center text-white font-black text-sm shadow-md">
                      N
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-sm text-white">NEXORA</span>
                        <div className="w-3.5 h-3.5 rounded-full bg-brand-500 flex items-center justify-center text-white text-[9px]">
                          ✓
                        </div>
                      </div>
                      <span className="text-xs text-slate-400 flex items-center gap-1">
                        منذ دقائق • <Globe className="w-3 h-3 text-slate-400" />
                      </span>
                    </div>
                  </div>
                </div>

                {/* FB Caption Body */}
                <div className="px-3.5 pb-3 text-sm text-slate-200 leading-relaxed whitespace-pre-line text-start dir-rtl">
                  {previewPost.caption}
                </div>

                {/* FB Image Asset */}
                {previewPost.image_path && (
                  <div className="bg-black">
                    <img
                      src={previewPost.image_path}
                      alt={previewPost.headline}
                      className="w-full object-contain max-h-[500px] mx-auto"
                    />
                  </div>
                )}

                {/* FB Interaction Bar */}
                <div className="p-3 border-t border-slate-800 text-xs text-slate-400 flex items-center justify-between">
                  <span>👍 ❤️ 58 إعجاب</span>
                  <span>14 تعليق • 6 مشاركات</span>
                </div>

                <div className="px-2 py-1.5 border-t border-slate-800/80 grid grid-cols-3 text-center text-xs text-slate-400 font-semibold">
                  <span className="py-2 hover:bg-slate-800/60 rounded-lg cursor-pointer">👍 أعجبني</span>
                  <span className="py-2 hover:bg-slate-800/60 rounded-lg cursor-pointer">💬 تعليق</span>
                  <span className="py-2 hover:bg-slate-800/60 rounded-lg cursor-pointer">↗️ مشاركة</span>
                </div>
              </div>
            </div>

            {/* Actions in preview modal */}
            <div className="p-4 border-t border-slate-800 flex items-center justify-end gap-3">
              <button
                onClick={() => setPreviewPost(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white cursor-pointer"
              >
                إغلاق
              </button>
              {previewPost.publishing_status !== 'PUBLISHED' && (
                <button
                  onClick={() => {
                    const p = previewPost;
                    setPreviewPost(null);
                    handlePublishNow(p);
                  }}
                  className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer shadow-md"
                >
                  <Send className="w-3.5 h-3.5" />
                  نشر الآن على الصفحة
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 2. Edit Caption Modal */}
      {/* ------------------------------------------------------------- */}
      {editingPost && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-amber-400" />
                تعديل النص التسويقي والعنوان
              </h3>
              <button
                onClick={() => setEditingPost(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">العنوان الرئيسي (Headline)</label>
              <input
                type="text"
                value={editHeadline}
                onChange={e => setEditHeadline(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-white focus:outline-hidden focus:border-brand-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">نص المنشور (Facebook Caption)</label>
              <textarea
                rows={8}
                value={editCaption}
                onChange={e => setEditCaption(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-sm text-white focus:outline-hidden focus:border-brand-500 leading-relaxed font-sans"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">
                تذكر: يُفضل عدم استخدام الإيموجي للحفاظ على الطابع المؤسسي لـ NEXORA.
              </span>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                onClick={() => setEditingPost(null)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white cursor-pointer"
              >
                إلغاء
              </button>
              <button
                onClick={handleSaveEdit}
                className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-md cursor-pointer"
              >
                حفظ التعديلات
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 3. Settings & Facebook Connection Modal */}
      {/* ------------------------------------------------------------- */}
      {showSettingsModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-xl w-full p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <SettingsIcon className="w-5 h-5 text-brand-400" />
                إعدادات التسويق والربط بـ Meta Graph API
              </h3>
              <button
                onClick={() => setShowSettingsModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Automation Toggles */}
            <div className="space-y-3 bg-slate-950/60 border border-slate-800/80 rounded-2xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm font-bold text-white block">التوليد التلقائي اليومي</span>
                  <span className="text-xs text-slate-400">توليد بوستر ومحتوى تسويقي واحد يومياً</span>
                </div>
                <input
                  type="checkbox"
                  checked={formAutoGen}
                  onChange={e => setFormAutoGen(e.target.checked)}
                  className="w-5 h-5 rounded-md accent-brand-600 cursor-pointer"
                />
              </div>

              <div className="flex items-center justify-between border-t border-slate-800/60 pt-3">
                <div>
                  <span className="text-sm font-bold text-white block">النشر التلقائي على فيسبوك</span>
                  <span className="text-xs text-slate-400">نشر البوست تلقائياً في موعد النشر المحدد</span>
                </div>
                <input
                  type="checkbox"
                  checked={formAutoPub}
                  onChange={e => setFormAutoPub(e.target.checked)}
                  className="w-5 h-5 rounded-md accent-brand-600 cursor-pointer"
                />
              </div>
            </div>

            {/* Timing Controls */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">موعد التوليد (بتوقيت القاهرة)</label>
                <input
                  type="time"
                  value={formGenTime}
                  onChange={e => setFormGenTime(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">موعد النشر (بتوقيت القاهرة)</label>
                <input
                  type="time"
                  value={formPubTime}
                  onChange={e => setFormPubTime(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white focus:outline-hidden"
                />
              </div>
            </div>

            {/* Meta Graph API Credentials */}
            <div className="space-y-3 border-t border-slate-800 pt-3">
              <h4 className="text-sm font-bold text-white flex items-center gap-2">
                <Share2 className="w-4 h-4 text-indigo-400" />
                بيانات صفحة فيسبوك (Facebook Page)
              </h4>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">Facebook Page ID</label>
                <input
                  type="text"
                  placeholder="مثال: 104859281928374"
                  value={formPageId}
                  onChange={e => setFormPageId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Page Access Token (رمز وصول الصفحة الدائم)
                </label>
                <input
                  type="password"
                  placeholder={settings?.has_facebook_token ? '••••••••••••••••••••••••••••••••' : 'أدخل رمز وصول الصفحة'}
                  value={formAccessToken}
                  onChange={e => setFormAccessToken(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white focus:outline-hidden"
                />
              </div>

              <div className="flex items-center gap-3 pt-1">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testingConnection}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5"
                >
                  {testingConnection ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <ShieldCheck className="w-3.5 h-3.5 text-brand-400" />
                  )}
                  فحص الاتصال بـ Meta API
                </button>

                {testResult && (
                  <span className={`text-xs font-semibold flex items-center gap-1.5 ${testResult.connected ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {testResult.connected ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                    {testResult.message}
                  </span>
                )}
              </div>
            </div>

            {/* AI Providers Info */}
            <div className="bg-slate-950/40 border border-slate-800/60 rounded-xl p-3 text-xs text-slate-400 space-y-1">
              <p><strong className="text-slate-300">مزود النصوص:</strong> Google Gemini API ({settings?.text_model || 'gemini-1.5-flash'})</p>
              <p><strong className="text-slate-300">مزود الصور:</strong> Cloudflare Workers AI ({settings?.image_model || 'flux-1-schnell'})</p>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <button
                onClick={() => setShowSettingsModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white cursor-pointer"
              >
                إغلاق
              </button>
              <button
                onClick={handleSaveSettings}
                disabled={savingSettings}
                className="px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold shadow-md cursor-pointer disabled:opacity-50"
              >
                {savingSettings ? 'جاري الحفظ...' : 'حفظ الإعدادات'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 4. Activity Logs Modal */}
      {/* ------------------------------------------------------------- */}
      {showLogsModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-brand-400" />
                سجل العمليات التسويقية (Audit Logs)
              </h3>
              <button
                onClick={() => setShowLogsModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {logs.length === 0 ? (
                <p className="text-center py-10 text-xs text-slate-500">لا توجد سجلات بعد.</p>
              ) : (
                logs.map(log => (
                  <div
                    key={log.id}
                    className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 flex items-start justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded-md font-bold text-[10px] ${
                          log.status === 'SUCCESS' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                          log.status === 'ERROR' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                          'bg-slate-800 text-slate-300'
                        }`}>
                          {log.status}
                        </span>
                        <span className="font-bold text-white">{log.action}</span>
                      </div>
                      {log.error_message && (
                        <p className="text-rose-400">{log.error_message}</p>
                      )}
                      {log.details && (
                        <p className="text-slate-400 font-mono text-[11px]">{JSON.stringify(log.details)}</p>
                      )}
                    </div>
                    <span className="text-[11px] text-slate-500 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString('ar-EG')}
                    </span>
                  </div>
                ))
              )}
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setShowLogsModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:text-white cursor-pointer"
              >
                إغلاق
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

