import React, { useState, useRef, useEffect } from 'react';
import {
  Mic, MicOff, Volume2, VolumeX, Sparkles, CheckCircle2, AlertTriangle,
  X, RefreshCw, Send, MessageSquare, Radio, Calendar,
  DollarSign, MapPin, ExternalLink, ShieldCheck, Check, Bot, User
} from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useVoiceLoop } from '../../hooks/useVoiceLoop'; // put useVoiceLoop.ts in src/hooks/

// TODO: point these at your real API base URL / token storage (same ones ../../api/client uses)
const API_BASE: string = (import.meta as any).env?.VITE_API_URL || '/api/v1';
function authHeaders(): Record<string, string> {
  const t =
    localStorage.getItem('access_token') ||
    localStorage.getItem('token') ||
    localStorage.getItem('accessToken');
  return t ? { Authorization: `Bearer ${t}` } : {};
}

interface VoiceFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  audioText?: string;
  timestamp?: string;
}

export const VoiceFormModal: React.FC<VoiceFormModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const { isRtl } = useAuth();

  // Mode: 'voice' (ChatGPT Voice mode orb) | 'chat' (Text + Voice transcript list)
  const [activeTab, setActiveTab] = useState<'voice' | 'chat'>('voice');

  // Conversation history & state
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'أهلاً بك! أنا مساعد Nexora الصوتي. اتفضل احكيلي عن مكالمتك أو معاينتك مع العميل وسأقوم بتسجيلها وتحديث ملفه فوراً.',
      audioText: 'أهلاً بك يا فندم! أنا مساعد Nexora الصوتي. اتفضل احكيلي عن مكالمتك أو معاينتك مع العميل وسأقوم بتسجيلها وتحديث ملفه فوراً.',
    }
  ]);
  const [currentContext, setCurrentContext] = useState<Record<string, any>>({});
  const [conversationState, setConversationState] = useState<'COLLECTING_INFO' | 'READY_FOR_CONFIRMATION' | 'CONFIRMED'>('COLLECTING_INFO');
  const [missingFields, setMissingFields] = useState<string[]>([]);
  const [confirmationPreview, setConfirmationPreview] = useState<any>(null);
  const [ambiguities, setAmbiguities] = useState<string[]>([]);

  // Audio & Voice State
  const [isProcessing, setIsProcessing] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [interimText, setInterimText] = useState('');
  const [textInput, setTextInput] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // CRM Saving state
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccessResult, setSaveSuccessResult] = useState<any>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Hands-free voice loop: listen (until you stop talking) -> Whisper -> assistant -> speak -> listen again.
  // NOTE: must stay ABOVE the `if (!isOpen) return null` below (rules of hooks).
  const voice = useVoiceLoop({
    silenceMs: 1500, // how long you must stay silent before your turn ends
    transcribe: async (blob) => {
      // Guard: blobs under ~8 KB are almost certainly silence or noise — skip them.
      // This prevents Whisper from hallucinating text from empty audio.
      if (blob.size < 8000) {
        console.debug(`[VoiceModal] Skipping tiny audio blob (${blob.size} bytes) — likely silence.`);
        return '';
      }

      const fd = new FormData();
      // Detect actual mimeType from the blob; fall back to audio/webm.
      // Whisper needs the correct extension to identify the codec (webm, mp4, ogg, wav).
      const mimeType = blob.type || 'audio/webm';
      const ext = mimeType.includes('mp4') ? 'mp4'
        : mimeType.includes('ogg') ? 'ogg'
          : mimeType.includes('wav') ? 'wav'
            : 'webm';
      // Re-wrap blob with explicit mimeType so FormData sends the right Content-Type
      const audioBlob = new Blob([blob], { type: mimeType });
      fd.append('file', audioBlob, `turn.${ext}`);
      fd.append('language', 'ar');
      const r = await fetch(`${API_BASE}/voice/transcribe`, { method: 'POST', body: fd, headers: authHeaders() });
      if (!r.ok) throw new Error(`transcribe ${r.status}`);
      const text: string = (await r.json()).transcript || '';
      setInterimText(text);
      return text;
    },
    synthesize: async (text) => {
      const r = await fetch(`${API_BASE}/voice/tts`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!r.ok) throw new Error(`tts ${r.status}`);
      return r.blob();
    },
    onUtterance: (text) => submitTurnMessage(text),
  });

  const isRecording = voice.state === 'listening' || voice.state === 'hearing';
  const isHearing = voice.state === 'hearing';
  const isSpeaking = voice.state === 'speaking';
  const audioLevel = voice.level;

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing]);

  // Clean up audio on close
  useEffect(() => {
    if (!isOpen) {
      voice.stop();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  /* ──────────────── Voice controls (hands-free loop) ──────────────── */

  function stopSpeaking() {
    voice.stopSpeaking();
  }

  async function speakText(text: string) {
    if (!autoSpeak) return;
    await voice.speak(text);
  }

  function startVoiceRecording() {
    setErrorMessage(null);
    setInterimText('');
    voice.start().catch((err: any) => {
      console.error('Mic access error:', err);
      setErrorMessage('لم يتم السماح بالوصول إلى الميكروفون. يرجى تفعيل إذن الميكروفون من إعدادات المتصفح.');
    });
  }

  function stopVoiceRecording() {
    voice.stop();
    setInterimText('');
  }

  function onOrbClick() {
    if (voice.state === 'idle') startVoiceRecording();
    else if (voice.state === 'hearing') voice.finishTurn(); // "I'm done talking"
    else if (voice.state === 'speaking') voice.stopSpeaking(); // interrupt the assistant
    else voice.stop();
  }

  /* ─────────────── Multi-Turn Conversation Submission ─────────────── */

  async function submitTurnMessage(userText: string) {
    if (!userText.trim() || isProcessing) return;

    // Check if user is confirming verbally
    const lower = userText.trim().toLowerCase();
    const verbalConfirm = [
      'اعتمد وسجل', 'اعتمد', 'احفظ في السي ار ام', 'احفظ في السي آر إم', 'احفظ في crm',
      'سجل في crm', 'سجل في السي آر إم', 'تمام احفظ',
    ].some(k => lower.includes(k));
    if (verbalConfirm && confirmationPreview && currentContext.lead_id) {
      await handleConfirmAndSave();
      return;
    }

    const newMessages: ChatMessage[] = [
      ...messages,
      { role: 'user', content: userText }
    ];
    setMessages(newMessages);
    setTextInput('');
    setIsProcessing(true);
    setErrorMessage(null);

    let spoken: string | undefined;
    try {
      const res = await api.post<any>('/voice/conversation', {
        messages: newMessages.map(m => ({ role: m.role, content: m.content })),
        current_context: currentContext,
        target_form: 'activity'
      });

      // Update multi-turn memory and state
      setCurrentContext(res.extracted_context || {});
      setConversationState(res.conversation_state || 'COLLECTING_INFO');
      setMissingFields(res.missing_fields || []);
      setConfirmationPreview(res.confirmation_preview || null);
      setAmbiguities(res.ambiguities || []);

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: res.reply_text,
        audioText: res.reply_audio_text
      };
      setMessages([...newMessages, assistantMsg]);
      spoken = res.reply_audio_text;
    } catch (err: any) {
      setErrorMessage(`حدث خطأ أثناء المحادثة: ${err.message || 'تعذر الاتصال بالخادم'}`);
    } finally {
      setIsProcessing(false);
      setInterimText('');
    }

    // Speak AFTER processing is done, and wait until finished so the mic never hears the assistant
    if (spoken) await speakText(spoken);
  }

  /* ─────────────── CRM Explicit Confirmation and Save ─────────────── */

  async function handleConfirmAndSave() {
    if (!currentContext?.lead_id) {
      setErrorMessage('يرجى تحديد العميل أولاً قبل الحفظ في النظام.');
      return;
    }

    stopSpeaking();
    setIsSaving(true);
    setErrorMessage(null);

    try {
      const res = await api.post<any>('/voice/confirm-and-save', {
        extracted_context: currentContext,
        explicit_confirmation: true
      });

      setSaveSuccessResult(res);
      setConversationState('CONFIRMED');

      const successAnnouncement = `تم الاعتماد بنجاح يا فندم! تم حفظ المعاينة في ملف العميل ${res.lead_name} وجدولة المتابعة القادمة في CRM.`;
      setIsSaving(false);
      setTimeout(() => {
        onSuccess?.();
      }, 2500);
      await speakText(successAnnouncement);
    } catch (err: any) {
      setErrorMessage(`فشل الحفظ في CRM: ${err.message || 'خطأ في التحقق من البيانات'}`);
    } finally {
      setIsSaving(false);
    }
  }

  /* ─────────────── UI Components ─────────────── */

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/85 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-2xl w-full h-[90vh] max-h-[720px] flex flex-col shadow-2xl relative overflow-hidden text-start">

        {/* Background glow orb */}
        <div className="absolute top-0 end-0 w-80 h-80 bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 start-0 w-72 h-72 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* ── Top Header Bar ── */}
        <div className="px-5 py-3.5 border-b border-slate-800/80 flex items-center justify-between z-10 shrink-0 bg-slate-900/60 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all ${isRecording ? 'bg-rose-500 text-white animate-pulse shadow-lg shadow-rose-500/30' :
              isSpeaking ? 'bg-brand-500 text-white animate-bounce' :
                'bg-brand-500/20 text-brand-400'
              }`}>
              <Radio className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-sm sm:text-base text-white">المساعد الصوتي الذكي (Voice AI Mode)</h3>
                <span className="text-[10px] bg-brand-500/20 text-brand-300 px-2 py-0.5 rounded-full border border-brand-500/30">
                  Qwen 3.8
                </span>
              </div>
              <p className="text-xs text-slate-400">محادثة صوتية ونصية تفاعلية باللهجة المصرية لإدارة الأنشطة والمعاينات</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Auto-speak toggle */}
            <button
              onClick={() => {
                const next = !autoSpeak;
                setAutoSpeak(next);
                if (!next) stopSpeaking();
              }}
              className={`p-2 rounded-xl text-xs font-medium border transition-colors ${autoSpeak
                ? 'bg-brand-600/20 text-brand-300 border-brand-500/30'
                : 'bg-slate-800 text-slate-400 border-slate-700'
                }`}
              title={autoSpeak ? 'تعطيل الرد الصوتي' : 'تفعيل الرد الصوتي'}
            >
              {autoSpeak ? <Volume2 className="w-4 h-4 text-brand-400" /> : <VolumeX className="w-4 h-4" />}
            </button>

            {/* View Mode Toggle: Voice Orb vs Chat List */}
            <div className="flex items-center bg-slate-800/80 p-0.5 rounded-xl border border-slate-700/60 text-xs">
              <button
                onClick={() => setActiveTab('voice')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-all ${activeTab === 'voice' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
                  }`}
              >
                صوت
              </button>
              <button
                onClick={() => setActiveTab('chat')}
                className={`px-3 py-1.5 rounded-lg font-medium transition-all ${activeTab === 'chat' ? 'bg-brand-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
                  }`}
              >
                شات
              </button>
            </div>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white p-1.5 rounded-xl hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* ── Main View Area ── */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 flex flex-col justify-between">

          {activeTab === 'voice' ? (
            /* ──────────────── Voice Mode: Pulsing ChatGPT Orb ──────────────── */
            <div className="flex-1 flex flex-col items-center justify-center my-auto space-y-6">

              {/* Animated Orb */}
              <div className="relative flex items-center justify-center">
                {/* Glow rings */}
                <div className={`absolute rounded-full transition-all duration-300 ${isRecording
                  ? 'w-48 h-48 bg-rose-500/20 animate-ping'
                  : isSpeaking
                    ? 'w-52 h-52 bg-brand-500/20 animate-pulse'
                    : 'w-40 h-40 bg-indigo-500/10'
                  }`} />
                <div className={`absolute rounded-full transition-all duration-500 ${isRecording
                  ? 'w-40 h-40 bg-gradient-to-tr from-rose-600 to-amber-500 opacity-30 blur-xl animate-pulse'
                  : isSpeaking
                    ? 'w-44 h-44 bg-gradient-to-tr from-brand-600 to-emerald-500 opacity-40 blur-xl animate-pulse'
                    : 'w-36 h-36 bg-gradient-to-tr from-brand-600 to-indigo-600 opacity-20 blur-xl'
                  }`} />

                {/* Central Circle button */}
                <button
                  onClick={onOrbClick}
                  style={{ transform: isRecording ? `scale(${1 + Math.min(audioLevel, 60) / 300})` : undefined }}
                  className={`relative z-10 w-28 h-28 sm:w-32 sm:h-32 rounded-full flex flex-col items-center justify-center transition-all shadow-2xl active:scale-95 ${isRecording
                    ? 'bg-gradient-to-tr from-rose-600 to-rose-500 text-white shadow-rose-600/40 ring-4 ring-rose-500/30 scale-105'
                    : isSpeaking
                      ? 'bg-gradient-to-tr from-brand-600 via-indigo-600 to-emerald-600 text-white shadow-brand-600/40 ring-4 ring-brand-500/30'
                      : 'bg-gradient-to-tr from-slate-800 to-slate-700 text-slate-200 hover:text-white hover:from-slate-700 hover:to-slate-600 ring-2 ring-slate-700'
                    }`}
                >
                  {isProcessing || voice.state === 'thinking' ? (
                    <RefreshCw className="w-8 h-8 animate-spin text-amber-300" />
                  ) : isRecording ? (
                    <>
                      <Mic className="w-8 h-8 mb-1 animate-pulse" />
                      <span className="text-[11px] font-bold">{isHearing ? 'سامعك... (اضغط لو خلصت)' : 'اتفضل اتكلم'}</span>
                    </>
                  ) : isSpeaking ? (
                    <>
                      <Volume2 className="w-8 h-8 mb-1 animate-bounce" />
                      <span className="text-[11px] font-bold">اضغط للمقاطعة</span>
                    </>
                  ) : (
                    <>
                      <Mic className="w-8 h-8 mb-1 text-brand-400" />
                      <span className="text-[11px] font-medium text-slate-300">اضغط للبدء</span>
                    </>
                  )}
                </button>
              </div>

              {/* Status subtitle */}
              <div className="text-center max-w-md px-4">
                {isRecording ? (
                  <p className="text-sm font-semibold text-rose-300 flex items-center justify-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
                    <span>{isHearing ? 'كمّل كلامك، أنا سامعك...' : 'اتفضل اتكلم بالعامية المصرية...'}</span>
                  </p>
                ) : isSpeaking ? (
                  <p className="text-sm font-medium text-brand-300 flex items-center justify-center gap-2">
                    <Sparkles className="w-4 h-4 text-brand-400 animate-spin" />
                    <span>المساعد الصوتي يجيبك الآن...</span>
                  </p>
                ) : isProcessing || voice.state === 'thinking' ? (
                  <p className="text-sm font-medium text-amber-300 flex items-center justify-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-amber-400" />
                    <span>الذكاء الاصطناعي يحلل كلامك ويستخرج البيانات...</span>
                  </p>
                ) : (
                  <p className="text-xs text-slate-400">
                    يمكنك التحدث بالعامية المصرية بحرية (مثال: "عاينت شقة في التجمع مع أحمد محمود والعميل مش عاجبه السعر").
                  </p>
                )}

                {/* What the assistant understood from you (shown while it is thinking) */}
                {interimText && (
                  <div className="mt-3 p-2.5 rounded-xl bg-slate-950/70 border border-slate-800 text-xs text-slate-200 italic animate-pulse">
                    "{interimText}"
                  </div>
                )}
              </div>

              {/* Latest Assistant Spoken Response Snippet */}
              {messages.length > 1 && !isRecording && (
                <div className="w-full max-w-lg bg-slate-800/60 border border-slate-700/60 p-3.5 rounded-2xl text-xs sm:text-sm text-slate-200">
                  <div className="flex items-center gap-1.5 text-brand-300 font-bold mb-1 text-xs">
                    <Bot className="w-3.5 h-3.5" />
                    <span>رد المساعد:</span>
                  </div>
                  <p className="leading-relaxed">{messages[messages.length - 1].content}</p>
                </div>
              )}
            </div>
          ) : (
            /* ──────────────── Chat Mode: Conversation History ──────────────── */
            <div className="flex-1 overflow-y-auto space-y-3.5 pe-1">
              {messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex items-start gap-2.5 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {m.role === 'assistant' && (
                    <div className="w-7 h-7 rounded-lg bg-brand-600/20 text-brand-400 flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] rounded-2xl p-3 text-xs sm:text-sm leading-relaxed ${m.role === 'user'
                      ? 'bg-brand-600 text-white rounded-te-none'
                      : 'bg-slate-800/80 border border-slate-700/60 text-slate-200 rounded-ts-none'
                      }`}
                  >
                    <p className="whitespace-pre-wrap">{m.content}</p>
                    {m.role === 'assistant' && m.audioText && (
                      <button
                        onClick={() => voice.speak(m.audioText || m.content)}
                        className="mt-2 text-[10px] text-brand-300 hover:text-white flex items-center gap-1 opacity-80 hover:opacity-100 transition-opacity"
                      >
                        <Volume2 className="w-3 h-3" />
                        <span>إعادة الاستماع</span>
                      </button>
                    )}
                  </div>

                  {m.role === 'user' && (
                    <div className="w-7 h-7 rounded-lg bg-slate-700 text-slate-300 flex items-center justify-center shrink-0 mt-0.5">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              ))}

              {isProcessing && (
                <div className="flex items-center gap-2 text-xs text-brand-300 ps-1">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>المساعد يفكر ويستخرج البيانات...</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}

          {/* ── Ambiguities Banner (if multiple matching leads) ── */}
          {ambiguities.length > 0 && (
            <div className="my-2 p-3 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
              <div>
                <p className="font-bold">تنبيه تطابق العملاء:</p>
                {ambiguities.map((a, i) => (
                  <p key={i} className="mt-0.5">{a}</p>
                ))}
              </div>
            </div>
          )}

          {/* ── Error Banner ── */}
          {errorMessage && (
            <div className="my-2 p-3 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* ── Real-Time Confirmation Preview Card ── */}
          {confirmationPreview && (
            <div className="my-2 p-3.5 sm:p-4 rounded-2xl bg-slate-800/90 border border-brand-500/40 shadow-xl space-y-2.5">
              <div className="flex items-center justify-between pb-2 border-b border-slate-700/60">
                <span className="text-xs font-bold text-brand-300 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  بطاقة المراجعة قبل الحفظ الفعلي في CRM
                </span>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${conversationState === 'READY_FOR_CONFIRMATION'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-amber-500/20 text-amber-300'
                  }`}>
                  {conversationState === 'READY_FOR_CONFIRMATION' ? 'جاهز للاعتماد' : 'جاري جمع البيانات'}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">العميل المستهدف:</span>
                  <span className="font-bold text-emerald-400">{confirmationPreview.lead_name || 'لم يحدد'}</span>
                </div>
                <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">نوع النشاط:</span>
                  <span className="font-semibold text-slate-200">
                    {confirmationPreview.activity_type === 'VISIT' ? 'معاينة ميدانية' : 'مكالمة هاتفية'}
                  </span>
                </div>
                <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">الاعتراض المسجل:</span>
                  <span className="font-semibold text-rose-400">{confirmationPreview.objection || 'لا يوجد'}</span>
                </div>
                <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">ميزانية العميل:</span>
                  <span className="font-bold text-amber-300">
                    {confirmationPreview.customer_stated_budget
                      ? `${Number(confirmationPreview.customer_stated_budget).toLocaleString('ar-EG')} ج.م`
                      : 'غير محددة'}
                  </span>
                </div>
                <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">الموقع المفضل:</span>
                  <span className="font-semibold text-slate-300">{confirmationPreview.preferred_location || '—'}</span>
                </div>
                <div className="bg-slate-900/60 p-2 rounded-xl border border-slate-800">
                  <span className="text-slate-400 block text-[10px]">المتابعة القادمة:</span>
                  <span className="font-semibold text-indigo-300">
                    {confirmationPreview.suggested_followup_date
                      ? new Date(confirmationPreview.suggested_followup_date).toLocaleDateString('ar-EG', { weekday: 'short', month: 'short', day: 'numeric' })
                      : 'خلال 48 ساعة'}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              {saveSuccessResult ? (
                <div className="p-3 bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 rounded-xl text-xs font-bold flex items-center justify-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>{saveSuccessResult.message}</span>
                </div>
              ) : (
                <div className="pt-1 flex items-center justify-between gap-3">
                  <span className="text-[11px] text-slate-400">
                    يمكنك الاستمرار في التعديل بالصوت، أو الضغط على تأكيد للحفظ:
                  </span>
                  <button
                    onClick={handleConfirmAndSave}
                    disabled={isSaving || !confirmationPreview.lead_id}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition-all shadow-lg shadow-emerald-600/30 disabled:opacity-50 active:scale-95 shrink-0"
                  >
                    {isSaving ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>جاري الحفظ في CRM...</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        <span>تأكيد وحفظ في CRM</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ── Bottom Input Tray (Unified Voice & Text) ── */}
          <div className="pt-2 z-10 shrink-0">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                submitTurnMessage(textInput);
              }}
              className="flex items-center gap-2 bg-slate-950/70 border border-slate-800 rounded-2xl p-2 focus-within:border-brand-500/60 transition-colors"
            >
              {/* Mic Button in Tray */}
              <button
                type="button"
                onClick={() => (voice.state === 'idle' ? startVoiceRecording() : voice.stop())}
                className={`p-2.5 rounded-xl transition-all ${isRecording
                  ? 'bg-rose-600 text-white animate-pulse shadow-md shadow-rose-600/30'
                  : 'bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700'
                  }`}
                title={voice.state !== 'idle' ? 'إيقاف المحادثة الصوتية' : 'تحدث بالصوت'}
              >
                {voice.state !== 'idle' ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4 text-brand-400" />}
              </button>

              {/* Text Input */}
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                placeholder={voice.state !== 'idle' ? 'المحادثة الصوتية شغالة...' : 'أو اكتب رسالتك هنا واضغط إرسال...'}
                disabled={voice.state !== 'idle'}
                className="flex-1 bg-transparent border-0 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none px-2"
                dir="rtl"
              />

              {/* Send Text Button */}
              <button
                type="submit"
                disabled={!textInput.trim() || isProcessing}
                className="p-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white transition-all disabled:opacity-40"
                title="إرسال"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>

        </div>
      </div>
    </div>
  );
};