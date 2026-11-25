import React, { useState, useEffect } from 'react';
import { 
  Menu, Search, Bell, Mic, Sparkles, Languages, LogOut, 
  Check, ExternalLink, X 
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import { NotificationItem } from '../../types';

interface HeaderProps {
  onToggleSidebar: () => void;
  onOpenVoiceModal: () => void;
  onOpenBriefingModal: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  onToggleSidebar,
  onOpenVoiceModal,
  onOpenBriefingModal,
}) => {
  const { user, logout, language, setLanguage, isRtl, t } = useAuth();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (user) {
      api.get<NotificationItem[]>('/notifications')
        .then(setNotifications)
        .catch(console.error);
    }
  }, [user]);

  const unreadCount = notifications.filter(n => !n.is_read).length;

  const markAsRead = async (id: number) => {
    try {
      await api.post(`/notifications/${id}/read`);
      setNotifications(prev =>
        prev.map(n => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <header className="h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 sticky top-0 z-20 flex items-center justify-between px-4 sm:px-6">
      {/* Left side: Menu toggle + Search */}
      <div className="flex items-center gap-3 flex-1 max-w-xl">
        <button
          onClick={onToggleSidebar}
          className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-lg transition-colors"
          aria-label="Toggle Navigation"
        >
          <Menu className="w-5 h-5" />
        </button>

        {/* Global Search */}
        <div className="relative flex-1 hidden md:block">
          <Search className="w-4 h-4 text-slate-400 absolute top-3 start-3" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('search_placeholder')}
            className="w-full bg-slate-800/60 border border-slate-700/60 rounded-xl py-2 ps-9 pe-4 text-xs sm:text-sm text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-all"
          />
        </div>
      </div>

      {/* Right side Actions */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Daily Briefing Button */}
        <button
          onClick={onOpenBriefingModal}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-amber-500/10 to-amber-600/20 text-amber-300 border border-amber-500/30 hover:border-amber-500/60 transition-all shadow-sm shadow-amber-500/10"
          title="Daily Briefing"
        >
          <Sparkles className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
          <span className="hidden lg:inline">{t('daily_briefing')}</span>
        </button>

        {/* Voice Input Action Button */}
        <button
          onClick={onOpenVoiceModal}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold bg-brand-600/20 text-brand-300 border border-brand-500/30 hover:bg-brand-600/30 hover:border-brand-500/60 transition-all shadow-sm"
          title="Record via Voice"
        >
          <Mic className="w-3.5 h-3.5 text-brand-400" />
          <span className="hidden sm:inline">{t('voice_input')}</span>
        </button>

        {/* Language Switcher */}
        <button
          onClick={() => setLanguage(language === 'ar' ? 'en' : 'ar')}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800 border border-slate-800 transition-colors"
          title="Switch Language"
        >
          <Languages className="w-4 h-4 text-slate-400" />
          <span>{language === 'ar' ? 'English' : 'عربي'}</span>
        </button>

        {/* Notifications Popover Toggle */}
        <div className="relative">
          <button
            onClick={() => setIsNotifOpen(!isNotifOpen)}
            className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-lg transition-colors relative"
            aria-label="Notifications"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 end-1.5 w-4 h-4 bg-rose-500 text-white rounded-full text-[10px] font-bold flex items-center justify-center animate-pulse">
                {unreadCount}
              </span>
            )}
          </button>

          {/* Notifications Dropdown */}
          {isNotifOpen && (
            <div className={`absolute top-12 ${isRtl ? 'left-0' : 'right-0'} w-80 sm:w-96 bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-4 z-50 text-start animate-in fade-in zoom-in-95 duration-150`}>
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <h4 className="text-sm font-bold text-white">التنبيهات والإشعارات</h4>
                  {unreadCount > 0 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/30">
                      {unreadCount} جديد
                    </span>
                  )}
                </div>
                <button 
                  onClick={() => setIsNotifOpen(false)}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="divide-y divide-slate-800/60 max-h-80 overflow-y-auto mt-2">
                {notifications.length === 0 ? (
                  <p className="text-xs text-slate-500 py-6 text-center">لا توجد تنبيهات جديدة</p>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      className={`py-3 px-2 rounded-xl transition-colors ${
                        n.is_read ? 'opacity-60' : 'bg-slate-800/30'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <h5 className="text-xs font-semibold text-slate-200">{n.title}</h5>
                        {!n.is_read && (
                          <button
                            onClick={() => markAsRead(n.id)}
                            className="text-[10px] text-brand-400 hover:underline shrink-0"
                          >
                            تحديد كمقروء
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1">{n.message}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Sign out */}
        <button
          onClick={logout}
          className="p-2 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-colors"
          title={t('logout')}
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};
