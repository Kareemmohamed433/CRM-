import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, Users, Kanban, Building2, PhoneCall, 
  CheckSquare, Calendar, ArrowLeftRight, BarChart3, Bot, 
  Settings, ShieldAlert, Sparkles, Building, MessageSquare, UserCheck, MapPin, Megaphone
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onToggle }) => {
  const { user, t, isRtl } = useAuth();

  const navItems = [
    { to: '/', label: t('dashboard'), icon: LayoutDashboard },
    { to: '/conversations', label: t('conversations'), icon: MessageSquare },
    { to: '/leads', label: t('leads'), icon: Users },
    { to: '/pipeline', label: t('pipeline'), icon: Kanban },
    { 
      to: '/properties-management', 
      label: isRtl ? 'المناطق والمخزون العقاري' : 'Properties & Locations', 
      icon: Building2 
    },
    { 
      to: '/activities', 
      label: t('activities'), 
      icon: PhoneCall,
      roles: ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER']
    },
    { 
      to: '/my-tasks', 
      label: isRtl ? 'مهامي الشخصية' : 'My Tasks', 
      icon: CheckSquare,
    },
    { 
      to: '/followups', 
      label: isRtl ? 'مهام الفريق' : 'Team Tasks', 
      icon: CheckSquare,
      roles: ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER']
    },
    { to: '/calendar', label: t('calendar'), icon: Calendar },
    { to: '/transfers', label: t('transfers'), icon: ArrowLeftRight },
    { 
      to: '/agents', 
      label: t('agents'), 
      icon: UserCheck,
      roles: ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER', 'TEAM_LEADER']
    },
    { 
      to: '/reports', 
      label: t('reports'), 
      icon: BarChart3,
      roles: ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER', 'TEAM_LEADER']
    },
    { 
      to: '/marketing', 
      label: isRtl ? 'أستوديو التسويق الذكي' : 'AI Marketing Studio', 
      icon: Megaphone,
      roles: ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER']
    },
    { to: '/ai-assistant', label: t('ai_assistant'), icon: Bot, highlight: true },
    { to: '/settings', label: t('settings'), icon: Settings },
  ];

  const filteredNavItems = navItems.filter(item => {
    if (!item.roles) return true;
    return user ? item.roles.includes(user.role) : false;
  });

  return (
    <aside
      className={`fixed top-0 bottom-0 z-30 transition-all duration-300 ease-in-out bg-slate-900 border-slate-800 border-e flex flex-col ${
        isRtl ? 'right-0' : 'left-0'
      } ${isOpen ? 'w-64' : 'w-20'}`}
    >
      {/* Brand Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-slate-800">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-brand-500/20 shrink-0">
            <Building className="w-5 h-5" />
          </div>
          {isOpen && (
            <div className="flex flex-col truncate">
              <span className="font-bold text-base tracking-wide text-white truncate">
                Nexora CRM
              </span>
              <span className="text-xs text-brand-400 font-medium truncate">
                {user?.company_name || 'Enterprise Real Estate'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {filteredNavItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-brand-600 text-white shadow-sm shadow-brand-600/30'
                    : item.highlight
                    ? 'text-amber-400 hover:bg-slate-800/80 bg-slate-800/40'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                }`
              }
              title={!isOpen ? item.label : undefined}
            >
              <Icon className="w-5 h-5 shrink-0" />
              {isOpen && <span className="truncate">{item.label}</span>}
              {isOpen && item.highlight && (
                <Sparkles className="w-3.5 h-3.5 ms-auto text-amber-400 animate-pulse" />
              )}
            </NavLink>
          );
        })}
      </div>

      {/* Active User / Role Footer */}
      {user && (
        <div className="p-3 border-t border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-sm text-brand-400 shrink-0">
              {user.full_name.charAt(0)}
            </div>
            {isOpen && (
              <div className="truncate flex-1">
                <p className="text-xs font-semibold text-slate-200 truncate">
                  {user.full_name}
                </p>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  <span className="text-[10px] uppercase tracking-wider text-slate-400 font-medium truncate">
                    {user.role.replace('_', ' ')}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </aside>
  );
};
