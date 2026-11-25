import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { VoiceFormModal } from '../modals/VoiceFormModal';
import { DailyBriefingModal } from '../modals/DailyBriefingModal';
import { useAuth } from '../../context/AuthContext';
import { Bot, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [voiceModalOpen, setVoiceModalOpen] = useState(false);
  const [briefingModalOpen, setBriefingModalOpen] = useState(false);
  const { isRtl } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main Content Area */}
      <div
        className={`flex-1 flex flex-col transition-all duration-300 ease-in-out ${
          isRtl ? (sidebarOpen ? 'sm:mr-64 mr-20' : 'mr-20') : (sidebarOpen ? 'sm:ml-64 ml-20' : 'ml-20')
        }`}
      >
        <Header
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          onOpenVoiceModal={() => setVoiceModalOpen(true)}
          onOpenBriefingModal={() => setBriefingModalOpen(true)}
        />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>

      {/* Floating AI Assistant Trigger */}
      <button
        onClick={() => navigate('/ai-assistant')}
        className={`fixed bottom-6 ${
          isRtl ? 'left-6' : 'right-6'
        } z-30 flex items-center gap-2 px-4 py-3 rounded-full bg-gradient-to-r from-brand-600 via-indigo-600 to-brand-500 text-white font-bold text-xs shadow-xl shadow-brand-500/30 hover:scale-105 active:scale-95 transition-all`}
        title="Open AI Sales Assistant"
      >
        <Bot className="w-5 h-5" />
        <span className="hidden sm:inline">مساعد المبيعات الذكي</span>
        <Sparkles className="w-3.5 h-3.5 text-amber-300 animate-pulse" />
      </button>

      {/* Modals */}
      <VoiceFormModal
        isOpen={voiceModalOpen}
        onClose={() => setVoiceModalOpen(false)}
      />

      <DailyBriefingModal
        isOpen={briefingModalOpen}
        onClose={() => setBriefingModalOpen(false)}
      />
    </div>
  );
};
