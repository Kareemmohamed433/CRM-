import React, { useState, useEffect, useRef } from 'react';
import {
  MessageSquare, Search, Send, Mic, Volume2, ShieldCheck, UserCheck,
  Bot, User, Sparkles, Filter, Phone, CheckCircle2, AlertCircle,
  Clock, ArrowUpRight, Lock, Eye, Check, RefreshCw, Smartphone
} from 'lucide-react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import {
  Conversation, ConversationMessage, ConversationChannel, ConversationStatus,
  MessageSenderType, MessageType, User as UserType
} from '../types';

export const ConversationsPage: React.FC = () => {
  const { user, isRtl } = useAuth();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConvId, setSelectedConvId] = useState<number | null>(null);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [agents, setAgents] = useState<UserType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);

  // Filters
  const [selectedChannel, setSelectedChannel] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // New message form
  const [messageText, setMessageText] = useState('');
  const [isInternalNote, setIsInternalNote] = useState(false);

  // Audio playback state
  const [playingAudioId, setPlayingAudioId] = useState<number | null>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadConversations();
    loadAgents();
  }, [selectedChannel]);

  useEffect(() => {
    if (selectedConvId) {
      loadConversationDetail(selectedConvId);
    }
  }, [selectedConvId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeConversation?.messages]);

  const loadConversations = async () => {
    setIsLoading(true);
    try {
      const channelParam = selectedChannel !== 'ALL' ? `?channel=${selectedChannel}` : '';
      const data = await api.get<Conversation[]>(`/conversations${channelParam}`);
      setConversations(data);
      if (data.length > 0 && !selectedConvId) {
        setSelectedConvId(data[0].id);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadAgents = async () => {
    try {
      const data = await api.get<UserType[]>('/users');
      setAgents(data.filter(u => u.role === 'SALES_AGENT'));
    } catch (err) {
      console.error('Failed to load agents:', err);
    }
  };

  const loadConversationDetail = async (id: number) => {
    try {
      const data = await api.get<Conversation>(`/conversations/${id}`);
      setActiveConversation(data);
      // Update local unread counter in list
      setConversations(prev =>
        prev.map(c => c.id === id ? { ...c, unread_count: 0 } : c)
      );
    } catch (err) {
      console.error('Failed to load conversation detail:', err);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedConvId || !messageText.trim() || isSending) return;

    setIsSending(true);
    try {
      const newMsg = await api.post<ConversationMessage>(
        `/conversations/${selectedConvId}/messages`,
        {
          content: messageText.trim(),
          is_internal_note: isInternalNote,
          message_type: 'TEXT'
        }
      );

      if (activeConversation) {
        setActiveConversation({
          ...activeConversation,
          messages: [...(activeConversation.messages || []), newMsg],
          last_message_text: isInternalNote ? activeConversation.last_message_text : newMsg.content
        });
      }

      setMessageText('');
      setIsInternalNote(false);
      loadConversations();
    } catch (err) {
      console.error('Failed to send message:', err);
    } finally {
      setIsSending(false);
    }
  };

  const handleToggleTakeover = async () => {
    if (!selectedConvId || !activeConversation) return;
    const nextState = !activeConversation.human_takeover;
    try {
      await api.post(`/conversations/${selectedConvId}/takeover`, {
        human_takeover: nextState
      });
      setActiveConversation({
        ...activeConversation,
        human_takeover: nextState
      });
    } catch (err) {
      console.error('Failed to toggle takeover:', err);
    }
  };

  const handleAssignAgent = async (agentId: number) => {
    if (!selectedConvId || !activeConversation) return;
    try {
      await api.post(`/conversations/${selectedConvId}/assign`, {
        agent_id: agentId
      });
      const selectedAgent = agents.find(a => a.id === agentId);
      setActiveConversation({
        ...activeConversation,
        assigned_agent_id: agentId,
        assigned_agent_name: selectedAgent?.full_name
      });
      loadConversations();
    } catch (err) {
      console.error('Failed to assign agent:', err);
    }
  };

  const handleGenerateSummary = async () => {
    if (!selectedConvId) return;
    setIsSummarizing(true);
    try {
      const res = await api.post<{ summary: string }>(`/conversations/${selectedConvId}/summarize`);
      if (activeConversation) {
        setActiveConversation({
          ...activeConversation,
          ai_summary: res.summary
        });
      }
    } catch (err) {
      console.error('Failed to summarize:', err);
    } finally {
      setIsSummarizing(false);
    }
  };

  const handlePlayAudio = (msgId: number, audioUrl?: string) => {
    if (playingAudioId === msgId) {
      audioPlayerRef.current?.pause();
      setPlayingAudioId(null);
      return;
    }

    if (audioUrl) {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      const audio = new Audio(audioUrl);
      audioPlayerRef.current = audio;
      setPlayingAudioId(msgId);
      audio.onended = () => setPlayingAudioId(null);
      audio.onerror = () => setPlayingAudioId(null);
      audio.play().catch(() => setPlayingAudioId(null));
    }
  };

  const filteredConversations = conversations.filter(c => {
    if (!searchQuery.trim()) return true;
    const term = searchQuery.toLowerCase();
    return (
      c.customer_name.toLowerCase().includes(term) ||
      (c.customer_phone && c.customer_phone.includes(term)) ||
      c.last_message_text.toLowerCase().includes(term)
    );
  });

  const getChannelBadge = (ch: ConversationChannel) => {
    switch (ch) {
      case 'WHATSAPP':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">واتساب</span>;
      case 'FACEBOOK':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">فيسبوك</span>;
      case 'INSTAGRAM':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-pink-500/20 text-pink-400 border border-pink-500/30">انستغرام</span>;
      case 'VOICE':
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">مكالمة صوتية</span>;
      default:
        return <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-700 text-slate-300">موقع ويب</span>;
    }
  };

  return (
    <div className="h-[calc(100vh-5rem)] flex flex-col space-y-3">
      {/* ── Top Bar ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-4 rounded-2xl shadow-sm">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-brand-400" />
            صندوق المحادثات الموحد (Omnichannel Inbox)
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            إدارة فورية لمحادثات العملاء عبر واتساب، فيسبوك، والمكالمات الصوتية مع دعم الردود الذكية وتوزيع المهام
          </p>
        </div>

        {/* Channel Filters */}
        <div className="flex items-center gap-1.5 bg-slate-800/80 p-1 rounded-xl border border-slate-700/60 overflow-x-auto text-xs">
          {['ALL', 'WHATSAPP', 'FACEBOOK', 'INSTAGRAM', 'VOICE'].map(ch => (
            <button
              key={ch}
              onClick={() => setSelectedChannel(ch)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-all shrink-0 ${
                selectedChannel === ch
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {ch === 'ALL' ? 'جميع القنوات' : ch === 'WHATSAPP' ? 'واتساب' : ch === 'FACEBOOK' ? 'فيسبوك' : ch === 'INSTAGRAM' ? 'انستغرام' : 'صوت'}
            </button>
          ))}
        </div>
      </div>

      {/* ── Main Workspace: 3 Columns ── */}
      <div className="flex-1 grid grid-cols-12 gap-3 min-h-0 overflow-hidden">
        {/* ── Column 1: Conversations List (col-span-3) ── */}
        <div className="col-span-12 md:col-span-4 lg:col-span-3 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col overflow-hidden">
          {/* Search Bar */}
          <div className="p-3 border-b border-slate-800">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute top-2.5 start-3" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="ابحث بالاسم أو رقم الهاتف..."
                className="w-full bg-slate-800/60 border border-slate-700/60 rounded-xl py-1.5 ps-9 pe-3 text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:border-brand-500"
              />
            </div>
          </div>

          {/* List items */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-800/50">
            {isLoading ? (
              <div className="p-8 text-center text-xs text-slate-500">جاري تحميل المحادثات...</div>
            ) : filteredConversations.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">لا توجد محادثات مطابقة</div>
            ) : (
              filteredConversations.map(c => {
                const isSelected = c.id === selectedConvId;
                return (
                  <button
                    key={c.id}
                    onClick={() => setSelectedConvId(c.id)}
                    className={`w-full p-3.5 text-start transition-all flex items-start gap-3 ${
                      isSelected
                        ? 'bg-brand-600/15 border-s-4 border-brand-500'
                        : 'hover:bg-slate-800/40'
                    }`}
                  >
                    <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-sm text-brand-400 shrink-0">
                      {c.customer_name.charAt(0)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1 mb-1">
                        <span className="font-bold text-xs text-slate-200 truncate">{c.customer_name}</span>
                        <span className="text-[10px] text-slate-500 shrink-0">
                          {new Date(c.last_message_time).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 truncate mb-1.5">{c.last_message_text || 'لا توجد رسائل'}</p>
                      <div className="flex items-center justify-between">
                        {getChannelBadge(c.channel)}
                        {c.unread_count > 0 && (
                          <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-rose-500 text-white font-bold animate-pulse">
                            {c.unread_count}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </div>

        {/* ── Column 2: Chat Messages & Input (col-span-6) ── */}
        <div className="col-span-12 md:col-span-8 lg:col-span-6 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col overflow-hidden">
          {activeConversation ? (
            <>
              {/* Chat Header */}
              <div className="p-3.5 border-b border-slate-800 bg-slate-900/80 backdrop-blur flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-brand-600 to-indigo-600 text-white flex items-center justify-center font-bold text-sm">
                    {activeConversation.customer_name.charAt(0)}
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-white flex items-center gap-2">
                      <span>{activeConversation.customer_name}</span>
                      {getChannelBadge(activeConversation.channel)}
                    </h3>
                    <p className="text-xs text-slate-400">
                      {activeConversation.customer_phone || 'بدون رقم مسجل'} • المسؤول: {activeConversation.assigned_agent_name || 'غير معين'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Takeover Toggle */}
                  <button
                    onClick={handleToggleTakeover}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
                      activeConversation.human_takeover
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                        : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    }`}
                    title="التبديل بين الرد الآلي وتدخل الموظف البشري"
                  >
                    {activeConversation.human_takeover ? (
                      <>
                        <UserCheck className="w-3.5 h-3.5 text-amber-400" />
                        <span>تحكم بشري</span>
                      </>
                    ) : (
                      <>
                        <Bot className="w-3.5 h-3.5 text-emerald-400" />
                        <span>مساعد AI مفعل</span>
                      </>
                    )}
                  </button>

                  {/* AI Summary button */}
                  <button
                    onClick={handleGenerateSummary}
                    disabled={isSummarizing}
                    className="p-2 rounded-xl bg-slate-800 text-slate-300 hover:text-white border border-slate-700 transition-colors"
                    title="توليد ملخص تنفيذي للمحادثة بالذكاء الاصطناعي"
                  >
                    <Sparkles className={`w-4 h-4 text-amber-400 ${isSummarizing ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>

              {/* AI Summary Bar (if available) */}
              {activeConversation.ai_summary && (
                <div className="p-3 bg-gradient-to-r from-amber-500/10 via-brand-500/10 to-transparent border-b border-slate-800 text-xs text-amber-200 flex items-start gap-2">
                  <Sparkles className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <span className="font-bold">ملخص AI: </span>
                    <span>{activeConversation.ai_summary}</span>
                  </div>
                </div>
              )}

              {/* Chat Messages Timeline */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {activeConversation.messages?.map(m => {
                  const isCustomer = m.sender_type === 'CUSTOMER';
                  const isNote = m.is_internal_note;

                  return (
                    <div
                      key={m.id}
                      className={`flex flex-col ${isNote ? 'items-center my-2' : isCustomer ? 'items-start' : 'items-end'}`}
                    >
                      {isNote ? (
                        <div className="w-full max-w-md p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-amber-300">
                          <div className="flex items-center gap-1.5 font-bold mb-1">
                            <Lock className="w-3.5 h-3.5 text-amber-400" />
                            <span>ملاحظة داخلية خاصة (مرئية للفريق فقط)</span>
                            <span className="text-[10px] text-amber-400/70 ms-auto">
                              بواسطة {m.sender_name || 'موظف'}
                            </span>
                          </div>
                          <p className="text-slate-200">{m.content}</p>
                        </div>
                      ) : (
                        <div className={`max-w-[80%] rounded-2xl p-3 text-xs sm:text-sm leading-relaxed ${
                          isCustomer
                            ? 'bg-slate-800 text-slate-200 rounded-ts-none border border-slate-700/60'
                            : 'bg-brand-600 text-white rounded-te-none shadow-md shadow-brand-600/20'
                        }`}>
                          <div className="flex items-center justify-between gap-4 mb-1 text-[10px] opacity-75">
                            <span className="font-semibold">{isCustomer ? activeConversation.customer_name : m.sender_name || 'مستشار المبيعات'}</span>
                            <span>{new Date(m.created_at).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>

                          {m.audio_url ? (
                            <div className="flex items-center gap-2 py-1">
                              <button
                                onClick={() => handlePlayAudio(m.id, m.audio_url)}
                                className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center hover:bg-white/30 transition-colors"
                              >
                                <Volume2 className={`w-4 h-4 ${playingAudioId === m.id ? 'animate-bounce' : ''}`} />
                              </button>
                              <span className="text-xs">تسجيل صوتي ({m.audio_duration ? `${m.audio_duration}s` : 'صوتي'})</span>
                            </div>
                          ) : (
                            <p className="whitespace-pre-wrap">{m.content}</p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
                <div ref={messagesEndRef} />
              </div>

              {/* Chat Input Bar */}
              <div className="p-3 border-t border-slate-800 bg-slate-900/90">
                <div className="flex items-center justify-between mb-2 px-1">
                  <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={isInternalNote}
                      onChange={(e) => setIsInternalNote(e.target.checked)}
                      className="rounded border-slate-700 text-brand-600 focus:ring-brand-500"
                    />
                    <span className="flex items-center gap-1 font-medium">
                      <Lock className="w-3.5 h-3.5 text-amber-400" />
                      ملاحظة داخلية (لن تصل للعميل)
                    </span>
                  </label>
                  <span className="text-[11px] text-slate-400">
                    {isInternalNote ? 'تدوين داخلي خاص' : `الإرسال عبر ${activeConversation.channel}`}
                  </span>
                </div>

                <form onSubmit={handleSendMessage} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={messageText}
                    onChange={(e) => setMessageText(e.target.value)}
                    placeholder={isInternalNote ? 'اكتب ملاحظة داخلية للفريق...' : 'اكتب ردك للعميل بالعامية المصرية...'}
                    className={`flex-1 rounded-xl py-2 px-3.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 border focus:outline-none transition-all ${
                      isInternalNote
                        ? 'bg-amber-950/20 border-amber-500/40 focus:border-amber-500'
                        : 'bg-slate-800/80 border-slate-700/60 focus:border-brand-500'
                    }`}
                  />
                  <button
                    type="submit"
                    disabled={!messageText.trim() || isSending}
                    className={`p-2.5 rounded-xl text-white transition-all disabled:opacity-40 shadow-sm ${
                      isInternalNote
                        ? 'bg-amber-600 hover:bg-amber-500 shadow-amber-600/30'
                        : 'bg-brand-600 hover:bg-brand-500 shadow-brand-600/30'
                    }`}
                    title="إرسال"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500">
              <MessageSquare className="w-12 h-12 mb-3 text-slate-700" />
              <p className="text-sm font-semibold text-slate-400">اختر محادثة لعرض تفاصيلها</p>
            </div>
          )}
        </div>

        {/* ── Column 3: Customer Context & Lead Actions (col-span-3) ── */}
        <div className="hidden lg:flex col-span-3 bg-slate-900 border border-slate-800 rounded-2xl flex-col p-4 overflow-y-auto space-y-4">
          {activeConversation ? (
            <>
              <div>
                <h4 className="font-bold text-sm text-white mb-2 pb-2 border-b border-slate-800">
                  ملف العميل وسياق CRM
                </h4>
                <div className="space-y-2 text-xs">
                  <div className="p-2.5 rounded-xl bg-slate-800/50 border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">الاسم الكامل:</span>
                    <span className="font-bold text-slate-200">{activeConversation.customer_name}</span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-800/50 border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">رقم الهاتف:</span>
                    <span className="font-semibold text-emerald-400">{activeConversation.customer_phone || '—'}</span>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-800/50 border border-slate-800">
                    <span className="text-slate-400 block text-[10px]">العميل المحتمل المرتبط:</span>
                    <span className="font-semibold text-slate-300">
                      {activeConversation.lead_name || 'غير مربوط بملف عميل'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Assignment Selector */}
              <div>
                <h4 className="font-bold text-xs text-white mb-2">تعيين مستشار المبيعات:</h4>
                <select
                  value={activeConversation.assigned_agent_id || ''}
                  onChange={(e) => handleAssignAgent(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl py-2 px-3 text-xs text-slate-200 focus:outline-none focus:border-brand-500"
                >
                  <option value="">بدون تعيين (غير معين)</option>
                  {agents.map(ag => (
                    <option key={ag.id} value={ag.id}>{ag.full_name}</option>
                  ))}
                </select>
              </div>

              {/* Direct Actions */}
              <div className="pt-2 border-t border-slate-800 space-y-2">
                <h4 className="font-bold text-xs text-slate-400 mb-2">إجراءات سريعة:</h4>
                {activeConversation.customer_phone && (
                  <a
                    href={`https://wa.me/${activeConversation.customer_phone.replace(/\+/g, '')}`}
                    target="_blank"
                    rel="noreferrer"
                    className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-emerald-600/20 text-emerald-300 border border-emerald-500/30 text-xs font-semibold hover:bg-emerald-600/30 transition-all"
                  >
                    <Smartphone className="w-4 h-4 text-emerald-400" />
                    <span>فتح محادثة واتساب الرسمية</span>
                  </a>
                )}
                {activeConversation.lead_id && (
                  <a
                    href={`/leads/${activeConversation.lead_id}`}
                    className="w-full flex items-center justify-center gap-2 py-2 rounded-xl bg-brand-600/20 text-brand-300 border border-brand-500/30 text-xs font-semibold hover:bg-brand-600/30 transition-all"
                  >
                    <ArrowUpRight className="w-4 h-4 text-brand-400" />
                    <span>عرض الملف الكامل للعميل</span>
                  </a>
                )}
              </div>
            </>
          ) : (
            <p className="text-xs text-slate-500 text-center py-8">اختر محادثة لعرض ملف العميل</p>
          )}
        </div>
      </div>
    </div>
  );
};

