import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';
import { api } from '../api/client';

interface AuthContextType {
  user: User | null;
  token: string | null;
  language: 'ar' | 'en';
  isRtl: boolean;
  isLoading: boolean;
  login: (token: string, refreshToken: string, userData: User) => void;
  logout: () => void;
  setLanguage: (lang: 'ar' | 'en') => void;
  t: (key: string) => string;
}

const translations: Record<string, Record<string, string>> = {
  ar: {
    dashboard: 'لوحة التحكم',
    conversations: 'المحادثات الموحدة',
    agents: 'فريق المبيعات والوكلاء',
    leads: 'العملاء والطلبات',
    pipeline: 'مراحل البيع (Pipeline)',
    projects: 'المشاريع والمخزون',
    inventory: 'الوحدات المتاحة',
    activities: 'الأنشطة والمعاينات',
    followups: 'المتابعات والمهام',
    calendar: 'التقويم والمواعيد',
    transfers: 'تحويلات العملاء',
    reports: 'التقارير والأداء',
    settings: 'الإعدادات والربط',
    daily_briefing: 'الموجز اليومي للذكاء الاصطناعي',
    ai_assistant: 'المساعد الذكي',
    voice_input: 'تسجيل بالصوت',
    logout: 'تسجيل الخروج',
    search_placeholder: 'بحث سريع بالاسم، الهاتف، المشروع...',
    overdue_tasks: 'متابعات متأخرة',
    due_today: 'متابعات اليوم',
    today_visits: 'معاينات اليوم',
    new_leads: 'عملاء جدد',
    total_leads: 'إجمالي العملاء',
    won_deals: 'صفقات ناجحة',
    conversion_rate: 'معدل التحويل',
    add_lead: 'إضافة عميل جديد',
    record_visit: 'تسجيل نتيجة معاينة',
    find_alternatives: 'اقتراح وحدات بديلة',
  },
  en: {
    dashboard: 'Dashboard',
    conversations: 'Omnichannel Inbox',
    agents: 'Sales Agents',
    leads: 'Leads & Customers',
    pipeline: 'Sales Pipeline',
    projects: 'Projects & Inventory',
    inventory: 'Available Units',
    activities: 'Activities & Visits',
    followups: 'Follow-ups & Tasks',
    calendar: 'Calendar & Visits',
    transfers: 'Lead Transfers',
    reports: 'Reports & Analytics',
    settings: 'Settings & Integrations',
    daily_briefing: 'Daily AI Briefing',
    ai_assistant: 'AI Assistant',
    voice_input: 'Voice Input',
    logout: 'Sign Out',
    search_placeholder: 'Search by lead name, phone, project...',
    overdue_tasks: 'Overdue Follow-ups',
    due_today: 'Due Today',
    today_visits: "Today's Visits",
    new_leads: 'New Leads',
    total_leads: 'Total Leads',
    won_deals: 'Won Deals',
    conversion_rate: 'Conversion Rate',
    add_lead: 'New Lead',
    record_visit: 'Record Visit Outcome',
    find_alternatives: 'Find Alternative Units',
  }
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [language, setLanguageState] = useState<'ar' | 'en'>(
    (localStorage.getItem('crm_lang') as 'ar' | 'en') || 'ar'
  );
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const isRtl = language === 'ar';

  const setLanguage = (lang: 'ar' | 'en') => {
    setLanguageState(lang);
    localStorage.setItem('crm_lang', lang);
    document.documentElement.setAttribute('lang', lang);
    document.documentElement.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');
  };

  useEffect(() => {
    // Set initial dir & lang attribute
    document.documentElement.setAttribute('lang', language);
    document.documentElement.setAttribute('dir', isRtl ? 'rtl' : 'ltr');

    // Fetch user profile if token exists
    if (token) {
      api.get<User>('/auth/me')
        .then((userData) => {
          setUser(userData);
        })
        .catch(() => {
          logout();
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = (accessToken: string, refreshToken: string, userData: User) => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    setToken(accessToken);
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  };

  const t = (key: string): string => {
    return translations[language][key] || key;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        language,
        isRtl,
        isLoading,
        login,
        logout,
        setLanguage,
        t,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
