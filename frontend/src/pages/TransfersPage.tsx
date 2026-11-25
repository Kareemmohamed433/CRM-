import React, { useEffect, useState } from 'react';
import { 
  ArrowLeftRight, CheckCircle2, XCircle, Clock, 
  User, AlertCircle, ShieldCheck, ArrowRight 
} from 'lucide-react';
import { api } from '../api/client';
import { TransferRequest } from '../types';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export const TransfersPage: React.FC = () => {
  const [transfers, setTransfers] = useState<TransferRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [selectedTransfer, setSelectedTransfer] = useState<TransferRequest | null>(null);
  const [reviewApproved, setReviewApproved] = useState(true);
  const [reviewNotes, setReviewNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const { user } = useAuth();
  const navigate = useNavigate();

  const isReviewer = ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER', 'TEAM_LEADER'].includes(user?.role || '');

  const fetchTransfers = () => {
    setLoading(true);
    api.get<TransferRequest[]>('/transfers')
      .then(setTransfers)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTransfers();
  }, []);

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTransfer) return;
    setSubmitting(true);

    try {
      await api.post(`/transfers/${selectedTransfer.id}/review`, {
        approved: reviewApproved,
        review_notes: reviewNotes,
      });

      setReviewModalOpen(false);
      setSelectedTransfer(null);
      fetchTransfers();
    } catch (err: any) {
      alert(`خطأ: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 text-start">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-white flex items-center gap-2">
            <ArrowLeftRight className="w-6 h-6 text-amber-400" />
            <span>طلبات تحويل وإعادة إسناد العملاء (Lead Transfers)</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            حوكمة نقل العملاء بين المستشارين والفرق مع الاحتفاظ بكامل السجل التاريخي
          </p>
        </div>
      </div>

      {/* Transfers Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl shadow-xl overflow-hidden">
        {loading ? (
          <div className="py-20 text-center text-slate-400 text-xs animate-pulse">
            جاري تحميل طلبات النقل...
          </div>
        ) : transfers.length === 0 ? (
          <div className="py-20 text-center text-slate-400 text-xs">
            لا توجد طلبات نقل مسجلة حالياً.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-start">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-900/60">
                  <th className="py-3.5 px-4 font-semibold">العميل</th>
                  <th className="py-3.5 px-4 font-semibold">المستشار الحالي</th>
                  <th className="py-3.5 px-4 font-semibold">المستشار المطلوب</th>
                  <th className="py-3.5 px-4 font-semibold">سبب النقل</th>
                  <th className="py-3.5 px-4 font-semibold">مقدم الطلب</th>
                  <th className="py-3.5 px-4 font-semibold">الحالة</th>
                  <th className="py-3.5 px-4 font-semibold text-center">الإجراء</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {transfers.map((t) => (
                  <tr key={t.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-bold text-white">
                      <span 
                        onClick={() => navigate(`/leads/${t.lead_id}`)}
                        className="hover:text-brand-400 cursor-pointer"
                      >
                        {t.lead_name}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-slate-300">
                      {t.current_owner_name || 'غير مسند'}
                    </td>

                    <td className="py-3.5 px-4 font-semibold text-brand-300">
                      {t.requested_owner_name}
                    </td>

                    <td className="py-3.5 px-4 text-slate-300 max-w-xs">
                      <div>{t.reason}</div>
                      {t.notes && <div className="text-[10px] text-slate-400 mt-0.5">{t.notes}</div>}
                    </td>

                    <td className="py-3.5 px-4 text-slate-400">
                      {t.requested_by_name}
                    </td>

                    <td className="py-3.5 px-4">
                      {t.status === 'APPROVED' && (
                        <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 w-fit">
                          <CheckCircle2 className="w-3 h-3" />
                          معتمد (Approved)
                        </span>
                      )}
                      {t.status === 'REJECTED' && (
                        <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1 w-fit">
                          <XCircle className="w-3 h-3" />
                          مرفوض (Rejected)
                        </span>
                      )}
                      {t.status === 'PENDING' && (
                        <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1 w-fit">
                          <Clock className="w-3 h-3" />
                          قيد المراجعة (Pending)
                        </span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 text-center">
                      {t.status === 'PENDING' && isReviewer ? (
                        <button
                          onClick={() => {
                            setSelectedTransfer(t);
                            setReviewApproved(true);
                            setReviewModalOpen(true);
                          }}
                          className="px-3 py-1.5 rounded-lg text-xs font-bold bg-brand-600 hover:bg-brand-500 text-white shadow-md transition-all"
                        >
                          مراجعة واعتماد
                        </button>
                      ) : (
                        <span className="text-[11px] text-slate-500">
                          {t.reviewer_name ? `بواسطة ${t.reviewer_name}` : '—'}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Review Modal */}
      {reviewModalOpen && selectedTransfer && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl relative text-start">
            <h3 className="font-bold text-base text-white mb-1">مراجعة طلب نقل العميل</h3>
            <p className="text-xs text-slate-400 mb-4">
              نقل العميل <strong className="text-white">{selectedTransfer.lead_name}</strong> إلى المستشار <strong className="text-brand-300">{selectedTransfer.requested_owner_name}</strong>
            </p>

            <form onSubmit={handleReviewSubmit} className="space-y-4 text-xs">
              <div className="flex gap-4">
                <label className="flex items-center gap-2 cursor-pointer p-3 rounded-xl border flex-1 transition-all">
                  <input
                    type="radio"
                    name="decision"
                    checked={reviewApproved}
                    onChange={() => setReviewApproved(true)}
                    className="text-emerald-500"
                  />
                  <span className="font-bold text-emerald-400">موافقة واعتماد النقل</span>
                </label>

                <label className="flex items-center gap-2 cursor-pointer p-3 rounded-xl border flex-1 transition-all">
                  <input
                    type="radio"
                    name="decision"
                    checked={!reviewApproved}
                    onChange={() => setReviewApproved(false)}
                    className="text-rose-500"
                  />
                  <span className="font-bold text-rose-400">رفض الطلب</span>
                </label>
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">ملاحظات القرار والاعتماد</label>
                <textarea
                  rows={2}
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="ملاحظات المراجعة..."
                  className="w-full bg-slate-800 border border-slate-700 rounded-xl p-2.5 text-slate-100"
                />
              </div>

              <div className="pt-3 flex justify-end gap-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setReviewModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className={`px-5 py-2 rounded-xl text-xs font-bold text-white shadow-md ${
                    reviewApproved ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-rose-600 hover:bg-rose-500'
                  }`}
                >
                  {submitting ? 'جاري التنفيذ...' : 'تأكيد القرار'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
