import React, { useState, useRef, useEffect } from 'react';
import {
  Bot, Send, Sparkles, User, Mic, CheckCircle2,
  AlertCircle, ArrowRight, ShieldCheck, RefreshCw, ExternalLink,
  Activity, BarChart3, Volume2, Clock, Check, Play, Square
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { VoiceFormModal } from '../components/modals/VoiceFormModal';
import { VoiceAnalyticsData } from '../types';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  toolsCalled?: string[];
  actionDraft?: any;
  links?: Array<{ title: string; url: string }>;
}

export const AIAssistantPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'telemetry'>('chat');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'أهلاً بك! أنا مساعد Nexora الذكي لإدارة العقارات والمبيعات. يمكنني مساعدتك في استعراض متابعاتك المتأخرة، أو البحث في مخزون الوحدات المتاحة بميزانية محددة، أو تلخيص مهام اليوم وتجهيز مسودات المتابعة.',
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [executingAction, setExecutingAction] = useState(false);
  const [actionDone, setActionDone] = useState(false);
  const [voiceModalOpen, setVoiceModalOpen] = useState(false);
  // Server-side flow state (appointment/reminder/lead drafts). Must round-trip on every turn.
  const [conversationContext, setConversationContext] = useState<Record<string, any>>({});

  // Telemetry state
  const [telemetry, setTelemetry] = useState<VoiceAnalyticsData | null>(null);
  const [loadingTelemetry, setLoadingTelemetry] = useState(false);
  const [testText, setTestText] = useState('أهلاً بك في نيكسورا سي آر إم، جاهز لمساعدتك في إتمام الصفقات العقارية.');
  const [isPlayingTest, setIsPlayingTest] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioTestRef = useRef<HTMLAudioElement | null>(null);
  const navigate = useNavigate();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    if (activeTab === 'telemetry') {
      loadTelemetry();
    }
  }, [activeTab]);

  const loadTelemetry = async () => {
    setLoadingTelemetry(true);
    try {
      const data = await api.get<VoiceAnalyticsData>('/voice/metrics');
      setTelemetry(data);
    } catch (err) {
      console.error('Failed to load voice telemetry:', err);
    } finally {
      setLoadingTelemetry(false);
    }
  };

  const handleTestTTS = async () => {
    if (isPlayingTest) {
      audioTestRef.current?.pause();
      setIsPlayingTest(false);
      return;
    }

    try {
      setIsPlayingTest(true);
      const token = localStorage.getItem('access_token');
      const res = await fetch('/api/v1/voice/tts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify({
          text: testText,
          voice: 'ar-EG-SalmaNeural',
          rate: '+20%'
        })
      });

      if (!res.ok) {
        throw new Error(`TTS HTTP error: ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioTestRef.current = audio;
      audio.onended = () => {
        setIsPlayingTest(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setIsPlayingTest(false);
        URL.revokeObjectURL(url);
      };
      await audio.play();
    } catch (err: any) {
      alert(`فشل تشغيل الصوت التجريبي: ${err.message}`);
      setIsPlayingTest(false);
    }
  };

  const handleSend = async (textToSend?: string) => {
    const text = textToSend || input;
    if (!text.trim() || loading) return;

    const userMsg: ChatMessage = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.post<any>('/ai/chat', {
        messages: [...messages, userMsg].map(m => ({ role: m.role, content: m.content })),
        current_context: conversationContext,
      });

      // keep the flow state for the next turn
      setConversationContext(res.current_context ?? {});

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.reply,
          toolsCalled: res.suggested_tools_called,
          actionDraft: res.action_draft,
          links: res.related_links,
        }
      ]);
    } catch (err: any) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `عذراً، حدث خطأ أثناء معالجة الطلب: ${err.message}`
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteDraft = async (draft: any) => {
    // Operator flows (appointment, reminder, follow-up) are confirmed through the chat turn,
    // so the server-side draft in conversationContext stays the single source of truth.
    if (draft?.action_type === 'crm_action') {
      await handleSend('تأكيد');
      return;
    }
    setExecutingAction(true);
    try {
      const res = await api.post<any>('/ai/execute-action', { action: draft });
      setActionDone(true);
      setConversationContext({});
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: `✅ تم الاعتماد والتنفيذ بنجاح: ${res.message}`
        }
      ]);
    } catch (err: any) {
      alert(`فشل التنفيذ: ${err.message}`);
    } finally {
      setExecutingAction(false);
    }
  };

  const samplePrompts = [
    'وريني المتابعات المتأخرة عندي',
    'ما هي الشقق المتاحة في التجمع بميزانية أقل من 4 مليون؟',
    'لخص لي زيارات ومواعيد اليوم',
    'مين أكتر عميل جاهز للإغلاق في مرحلة التفاوض؟'
  ];

  return (
    <div className="h-[calc(100vh-5rem)] flex flex-col bg-slate-900 border border-slate-800 rounded-3xl overflow-hidden shadow-2xl text-start">
      {/* ── Top Header Bar with Tabs ── */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between shrink-0 bg-slate-900/80 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-brand-600 via-indigo-600 to-amber-500 text-white flex items-center justify-center shadow-lg shadow-brand-500/20">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <span>مساعد مبيعات Nexora AI</span>
              <span className="text-[10px] bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full border border-amber-500/30">
                Egyptian Arabic Speech + Tools
              </span>
            </h2>
            <p className="text-xs text-slate-400">تحليل المتابعات، فحص المخزون، ونطق الردود الصوتية بالعامية المصرية</p>
          </div>
        </div>

        {/* View Switcher: Chat vs Telemetry */}
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-slate-800/80 p-0.5 rounded-xl border border-slate-700/60 text-xs">
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-3 py-1.5 rounded-lg font-medium transition-all ${activeTab === 'chat' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
            >
              محادثة ذكية
            </button>
            <button
              onClick={() => setActiveTab('telemetry')}
              className={`px-3 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 ${activeTab === 'telemetry' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
                }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>مراقبة الصوت AI</span>
            </button>
          </div>

          <button
            onClick={() => setVoiceModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold bg-indigo-600 hover:bg-indigo-500 text-white transition-all shadow-md shadow-indigo-600/20"
          >
            <Mic className="w-3.5 h-3.5" />
            <span>Voice Mode</span>
          </button>
        </div>
      </div>

      {activeTab === 'telemetry' ? (
        /* ──────────────── TAB 2: Voice & AI Telemetry Dashboard ──────────────── */
        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-bold text-base text-white">مؤشرات استجابة الصوت والذكاء الاصطناعي (Telemetry Metrics)</h3>
              <p className="text-xs text-slate-400 mt-0.5">قياسات حية لدقة التعرف على الكلام المصري وسرعة النطق والاستجابة</p>
            </div>
            <button
              onClick={loadTelemetry}
              disabled={loadingTelemetry}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 text-slate-300 hover:text-white border border-slate-700 text-xs transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingTelemetry ? 'animate-spin' : ''}`} />
              <span>تحديث المقاييس</span>
            </button>
          </div>

          {telemetry && (
            <>
              {/* Gauges Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-2xl bg-slate-800/60 border border-slate-700/60 text-xs">
                  <span className="text-slate-400 block mb-1">دقة تحويل الصوت (STT):</span>
                  <span className="text-2xl font-black text-emerald-400">{telemetry.stt.success_rate}%</span>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-700/50">
                    <span>التأخير: {telemetry.stt.avg_latency_ms} ms</span>
                    <span>الطلبات: {telemetry.stt.total_requests}</span>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-800/60 border border-slate-700/60 text-xs">
                  <span className="text-slate-400 block mb-1">استجابة المحادثة (LLM):</span>
                  <span className="text-2xl font-black text-brand-400">{telemetry.llm.success_rate}%</span>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-700/50">
                    <span>التأخير: {telemetry.llm.avg_latency_ms} ms</span>
                    <span>الطلبات: {telemetry.llm.total_requests}</span>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-800/60 border border-slate-700/60 text-xs">
                  <span className="text-slate-400 block mb-1">توليد النطق العصبي (TTS):</span>
                  <span className="text-2xl font-black text-indigo-400">{telemetry.tts.success_rate}%</span>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-700/50">
                    <span>التأخير: {telemetry.tts.avg_latency_ms} ms</span>
                    <span>الطلبات: {telemetry.tts.total_requests}</span>
                  </div>
                </div>

                <div className="p-4 rounded-2xl bg-slate-800/60 border border-slate-700/60 text-xs">
                  <span className="text-slate-400 block mb-1">التكلفة التقديرية للاستهلاك:</span>
                  <span className="text-2xl font-black text-amber-300">${telemetry.estimated_cost_usd}</span>
                  <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 pt-2 border-t border-slate-700/50">
                    <span>الجلسات: {telemetry.total_turns}</span>
                    <span>المقاطعات: {telemetry.e2e.interrupted_count}</span>
                  </div>
                </div>
              </div>

              {/* Providers Status */}
              <div className="p-4 rounded-2xl bg-slate-800/40 border border-slate-700/60 space-y-3">
                <h4 className="font-bold text-xs text-white">المزودات والنماذج النشطة في البيئة الحالية:</h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Speech-to-Text (STT):</span>
                    <strong className="text-slate-200">Groq Whisper (whisper-large-v3-turbo)</strong>
                    <p className="text-[10px] text-emerald-400 mt-1">✓ مهيأ لمفردات العقارات المصرية</p>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Conversational Reasoning (LLM):</span>
                    <strong className="text-slate-200">Qwen 3.8 27B / Llama 3.3</strong>
                    <p className="text-[10px] text-emerald-400 mt-1">✓ دعم استدعاء أدوات CRM والتحقق</p>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">Text-to-Speech (TTS):</span>
                    <strong className="text-slate-200">Edge-TTS (ar-EG-SalmaNeural)</strong>
                    <p className="text-[10px] text-emerald-400 mt-1">✓ نطق مصري طبيعي + بديل المتصفح التلقائي</p>
                  </div>
                </div>
              </div>

              {/* Live Audio Synthesis Test Playground */}
              <div className="p-4 sm:p-5 rounded-2xl bg-slate-800/70 border border-brand-500/30 space-y-3">
                <div className="flex items-center gap-2">
                  <Volume2 className="w-4 h-4 text-brand-400" />
                  <h4 className="font-bold text-sm text-white">منصة الاختبار الفوري للنطق الصوتي (Live Audio Playground)</h4>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={testText}
                    onChange={(e) => setTestText(e.target.value)}
                    className="flex-1 bg-slate-900 border border-slate-700 rounded-xl py-2 px-3 text-xs text-slate-100 focus:outline-none focus:border-brand-500"
                  />
                  <button
                    onClick={handleTestTTS}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all ${isPlayingTest ? 'bg-rose-600 text-white' : 'bg-brand-600 hover:bg-brand-500 text-white'
                      }`}
                  >
                    {isPlayingTest ? (
                      <>
                        <Square className="w-3.5 h-3.5" />
                        <span>إيقاف</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5" />
                        <span>اختبار النطق الصوتي</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      ) : (
        /* ──────────────── TAB 1: Chat Mode ──────────────── */
        <>
          {/* Chat Messages scroll area */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex items-start gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-xl bg-brand-600/20 text-brand-400 border border-brand-500/30 flex items-center justify-center shrink-0 mt-0.5">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-[85%] rounded-2xl p-4 text-xs sm:text-sm leading-relaxed ${m.role === 'user'
                      ? 'bg-brand-600 text-white rounded-te-none shadow-md shadow-brand-600/20'
                      : 'bg-slate-800/80 border border-slate-700/60 text-slate-200 rounded-ts-none'
                    }`}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>

                  {/* Tool Call Pills */}
                  {m.toolsCalled && m.toolsCalled.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-slate-700/60">
                      {m.toolsCalled.map((tool, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                        >
                          <Sparkles className="w-3 h-3 text-indigo-400" />
                          <span>استدعاء أداة: {tool}</span>
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Action Draft Preview (Confirmation needed before mutation) */}
                  {m.actionDraft && !actionDone && (
                    <div className="mt-3 p-3 rounded-xl bg-slate-900 border border-amber-500/40 text-xs text-amber-200 space-y-2">
                      <div className="flex items-center gap-1.5 font-bold text-amber-400">
                        <ShieldCheck className="w-4 h-4" />
                        <span>مسودة إجراء CRM تتطلب موافقتك:</span>
                      </div>
                      <p className="text-slate-300">
                        النوع: <strong>{m.actionDraft.action_type}</strong> | العميل ID: <strong>{m.actionDraft.lead_id}</strong>
                      </p>
                      <button
                        onClick={() => handleExecuteDraft(m.actionDraft)}
                        disabled={executingAction}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all shadow-sm"
                      >
                        {executingAction ? <RefreshCw className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                        <span>تأكيد وتنفيذ الإجراء في CRM</span>
                      </button>
                    </div>
                  )}

                  {/* Related Links */}
                  {m.links && m.links.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-slate-700/60">
                      {m.links.map((link, i) => (
                        <a
                          key={i}
                          href={link.url}
                          className="inline-flex items-center gap-1 text-[11px] text-brand-300 hover:underline"
                        >
                          <span>{link.title}</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      ))}
                    </div>
                  )}
                </div>

                {m.role === 'user' && (
                  <div className="w-8 h-8 rounded-xl bg-slate-800 text-slate-300 border border-slate-700 flex items-center justify-center shrink-0 mt-0.5">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <RefreshCw className="w-4 h-4 animate-spin text-brand-400" />
                <span>جاري معالجة السؤال واستخراج بيانات CRM...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Quick Prompt Chips */}
          <div className="px-4 py-2 border-t border-slate-800/80 bg-slate-900/40 flex items-center gap-2 overflow-x-auto text-xs shrink-0">
            <span className="text-slate-500 font-semibold shrink-0">اقتراحات:</span>
            {samplePrompts.map((p, i) => (
              <button
                key={i}
                onClick={() => handleSend(p)}
                className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/80 shrink-0 transition-colors"
              >
                {p}
              </button>
            ))}
          </div>

          {/* Input box */}
          <div className="p-4 border-t border-slate-800 bg-slate-900">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="اكتب استفسارك أو أمرك بالعربية أو الإنجليزية..."
                className="flex-1 bg-slate-800/80 border border-slate-700 rounded-2xl py-3 px-4 text-xs sm:text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40"
              />
              <button
                type="button"
                onClick={() => setVoiceModalOpen(true)}
                title="بدء محادثة صوتية ذكية (ChatGPT Voice Mode)"
                className="w-11 h-11 rounded-2xl bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-indigo-300 hover:text-white flex items-center justify-center transition-all shadow-md shrink-0"
              >
                <Mic className="w-4 h-4" />
              </button>
              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="w-11 h-11 rounded-2xl bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white flex items-center justify-center transition-all shadow-md shrink-0"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </>
      )}

      {/* Voice Mode Modal */}
      <VoiceFormModal
        isOpen={voiceModalOpen}
        onClose={() => setVoiceModalOpen(false)}
        onSuccess={() => {
          setVoiceModalOpen(false);
          setMessages(prev => [
            ...prev,
            {
              role: 'assistant',
              content: '✅ تم حفظ التقرير والنشاط بنجاح في قاعدة بيانات الـ CRM.'
            }
          ]);
        }}
      />
    </div>
  );
};