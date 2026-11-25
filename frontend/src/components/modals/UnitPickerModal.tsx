import React, { useEffect, useState } from 'react';
import { Building2, Check, AlertCircle } from 'lucide-react';
import { api } from '../../api/client';

interface UnitOption {
    property_id: number;
    unit_number: string;
    project_name: string;
    location: string;
    bedrooms: number;
    area: number;
    total_price: number;
    currency: string;
    installment_plan?: string;
    match_score: number;
}

interface UnitPickerModalProps {
    isOpen: boolean;
    leadId: number;
    leadName: string;
    targetStage: 'RESERVATION' | 'WON';
    onClose: () => void;
    onConfirm: (propertyId: number) => Promise<void>;
}

export const UnitPickerModal: React.FC<UnitPickerModalProps> = ({
    isOpen, leadId, leadName, targetStage, onClose, onConfirm,
}) => {
    const [units, setUnits] = useState<UnitOption[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        if (!isOpen) return;
        setSelectedId(null);
        setError('');
        setLoading(true);
        api.get<UnitOption[]>(`/leads/${leadId}/available-units`)
            .then(setUnits)
            .catch((err: any) => setError(err.message || 'فشل تحميل الوحدات المتاحة'))
            .finally(() => setLoading(false));
    }, [isOpen, leadId]);

    if (!isOpen) return null;

    const title = targetStage === 'WON' ? 'اختيار الوحدة المباعة' : 'اختيار الوحدة المحجوزة';

    const handleConfirm = async () => {
        if (selectedId == null) return;
        setSubmitting(true);
        setError('');
        try {
            await onConfirm(selectedId);
        } catch (err: any) {
            setError(err.message || 'فشل تنفيذ العملية');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
            <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl text-start">
                <h3 className="font-bold text-base text-white flex items-center gap-2 mb-1">
                    <Building2 className="w-4 h-4 text-brand-400" />
                    {title}
                </h3>
                <p className="text-xs text-slate-400 mb-4">
                    العميل: <strong className="text-white">{leadName}</strong> — الوحدة هتتحجز له وتختفي من الوحدات المتاحة.
                </p>

                {error && (
                    <div className="mb-3 p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-start gap-1.5">
                        <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                        <span>{error}</span>
                    </div>
                )}

                <div className="max-h-80 overflow-y-auto space-y-2 pe-1">
                    {loading ? (
                        <p className="py-10 text-center text-xs text-slate-400 animate-pulse">جاري تحميل الوحدات المتاحة...</p>
                    ) : units.length === 0 ? (
                        <p className="py-10 text-center text-xs text-slate-500">لا توجد وحدات متاحة في المخزون حالياً.</p>
                    ) : (
                        units.map((u) => (
                            <button
                                type="button"
                                key={u.property_id}
                                onClick={() => setSelectedId(u.property_id)}
                                className={`w-full text-start p-3 rounded-2xl border transition-colors text-xs ${selectedId === u.property_id
                                    ? 'bg-brand-500/10 border-brand-500'
                                    : 'bg-slate-800/40 border-slate-800 hover:border-slate-600'
                                    }`}
                            >
                                <div className="flex items-start justify-between gap-2">
                                    <div>
                                        <p className="font-bold text-slate-100">الوحدة {u.unit_number} - {u.project_name}</p>
                                        <p className="text-[11px] text-slate-400 mt-0.5">
                                            {u.location} • {u.bedrooms} غرف • {u.area} م²
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                            {u.match_score}%
                                        </span>
                                        {selectedId === u.property_id && <Check className="w-4 h-4 text-brand-400" />}
                                    </div>
                                </div>
                                <div className="flex justify-between mt-1.5 pt-1.5 border-t border-slate-800 text-[11px]">
                                    <span className="font-black text-brand-300">{u.total_price.toLocaleString()} {u.currency}</span>
                                    <span className="text-slate-400">{u.installment_plan}</span>
                                </div>
                            </button>
                        ))
                    )}
                </div>

                <div className="pt-4 mt-4 flex justify-end gap-3 border-t border-slate-800">
                    <button
                        type="button"
                        onClick={onClose}
                        className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
                    >
                        إلغاء
                    </button>
                    <button
                        type="button"
                        disabled={selectedId == null || submitting}
                        onClick={handleConfirm}
                        className="px-5 py-2 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-white shadow-md"
                    >
                        {submitting ? 'جاري التنفيذ...' : targetStage === 'WON' ? 'تأكيد البيع' : 'تأكيد الحجز'}
                    </button>
                </div>
            </div>
        </div>
    );
};