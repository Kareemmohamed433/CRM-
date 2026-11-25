import React, { useEffect, useState } from 'react';
import { 
  Building2, MessageCircle, Send, CheckCircle2, AlertCircle, 
  Search, X, ExternalLink, Image as ImageIcon, Sparkles, DollarSign 
} from 'lucide-react';
import { api } from '../../api/client';
import { Property, PropertyMessageResponse, PropertyOffer } from '../../types';

interface SendPropertyOfferModalProps {
  isOpen: boolean;
  onClose: () => void;
  leadId: number;
  leadName: string;
  leadPhone: string;
  onSuccess?: () => void;
}

export const SendPropertyOfferModal: React.FC<SendPropertyOfferModalProps> = ({
  isOpen,
  onClose,
  leadId,
  leadName,
  leadPhone,
  onSuccess,
}) => {
  const [step, setStep] = useState<'SELECT' | 'PREVIEW' | 'SENT'>('SELECT');
  const [properties, setProperties] = useState<Property[]>([]);
  const [loadingProps, setLoadingProps] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null);
  const [customPrice, setCustomPrice] = useState<string>('');
  const [generating, setGenerating] = useState(false);
  const [messageData, setMessageData] = useState<PropertyMessageResponse | null>(null);
  const [editedMessage, setEditedMessage] = useState('');
  const [createdOffer, setCreatedOffer] = useState<PropertyOffer | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      setStep('SELECT');
      setSelectedProperty(null);
      setCustomPrice('');
      setMessageData(null);
      setEditedMessage('');
      setCreatedOffer(null);
      setError('');
      loadProperties();
    }
  }, [isOpen]);

  const loadProperties = () => {
    setLoadingProps(true);
    api.get<Property[]>('/properties?status=AVAILABLE')
      .then(setProperties)
      .catch((err) => setError(err.message || 'فشل تحميل الوحدات العقارية'))
      .finally(() => setLoadingProps(false));
  };

  if (!isOpen) return null;

  const filteredProperties = properties.filter((p) => {
    const q = search.toLowerCase();
    return (
      p.unit_number.toLowerCase().includes(q) ||
      (p.project_name && p.project_name.toLowerCase().includes(q)) ||
      p.location.toLowerCase().includes(q) ||
      p.property_type.toLowerCase().includes(q)
    );
  });

  const handleSelectProperty = (prop: Property) => {
    setSelectedProperty(prop);
    setCustomPrice(String(prop.total_price));
  };

  const handleGenerateMessage = async () => {
    if (!selectedProperty) return;
    setGenerating(true);
    setError('');

    try {
      const priceNum = customPrice ? parseFloat(customPrice) : selectedProperty.total_price;
      
      // 1. Generate pitch & WhatsApp URL via AI endpoint
      const res = await api.post<PropertyMessageResponse>('/ai/property-message', {
        customer_id: leadId,
        property_id: selectedProperty.id,
        custom_price: priceNum,
      });
      setMessageData(res);
      setEditedMessage(res.message_text);

      // 2. Create the PropertyOffer record in PREPARED status
      const offer = await api.post<PropertyOffer>(`/leads/${leadId}/property-offers`, {
        property_id: selectedProperty.id,
        custom_price: priceNum,
        message_text: res.message_text,
      });
      setCreatedOffer(offer);

      setStep('PREVIEW');
    } catch (err: any) {
      setError(err.message || 'حدث خطأ أثناء تجهيز العرض العقاري');
    } finally {
      setGenerating(false);
    }
  };

  const handleOpenWhatsApp = () => {
    if (!messageData) return;
    // Build URL with potentially edited text
    const digits = leadPhone.replace(/\D/g, '');
    let formattedPhone = digits;
    if (formattedPhone.startsWith('0020')) formattedPhone = formattedPhone.slice(2);
    else if (formattedPhone.startsWith('01') && formattedPhone.length === 11) formattedPhone = `2${formattedPhone}`;
    
    const textEncoded = encodeURIComponent(editedMessage);
    const url = `https://wa.me/${formattedPhone}?text=${textEncoded}`;
    window.open(url, '_blank');
  };

  const handleConfirmSent = async () => {
    if (!createdOffer) return;
    setConfirming(true);
    setError('');

    try {
      await api.post(`/property-offers/${createdOffer.id}/confirm-shared`);
      setStep('SENT');
      if (onSuccess) onSuccess();
    } catch (err: any) {
      setError(err.message || 'فشل تأكيد إرسال العرض');
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-2xl w-full p-6 shadow-2xl relative text-start flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <MessageCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">إرسال عرض عقاري عبر واتساب</h3>
              <p className="text-xs text-slate-400">
                العميل: <strong className="text-white">{leadName}</strong> ({leadPhone})
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="my-3 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          
          {step === 'SELECT' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">
                  الخطوة 1: اختر الوحدة العقارية المناسبة من المخزون
                </span>
                <span className="text-[11px] text-slate-400">
                  الوحدات المتاحة: {properties.length}
                </span>
              </div>

              {/* Search box */}
              <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute top-3 start-3" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="ابحث برقم الوحدة، المشروع، أو المنطقة..."
                  className="w-full bg-slate-800/80 border border-slate-700 rounded-xl py-2 ps-9 pe-4 text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                />
              </div>

              {/* Properties list */}
              {loadingProps ? (
                <div className="py-12 text-center text-xs text-slate-400 animate-pulse">
                  جاري تحميل الوحدات العقارية المتاحة...
                </div>
              ) : filteredProperties.length === 0 ? (
                <div className="py-10 text-center text-xs text-slate-400 bg-slate-800/40 rounded-2xl border border-slate-800">
                  لا توجد وحدات مطابقة للبحث
                </div>
              ) : (
                <div className="max-h-60 overflow-y-auto space-y-2 pe-1">
                  {filteredProperties.map((p) => {
                    const isSelected = selectedProperty?.id === p.id;
                    return (
                      <div
                        key={p.id}
                        onClick={() => handleSelectProperty(p)}
                        className={`p-3 rounded-2xl border cursor-pointer transition-all flex items-center justify-between ${
                          isSelected
                            ? 'bg-emerald-500/10 border-emerald-500/50 shadow-md ring-1 ring-emerald-500/30'
                            : 'bg-slate-800/40 border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs ${
                            isSelected ? 'bg-emerald-500 text-white' : 'bg-slate-700 text-slate-300'
                          }`}>
                            <Building2 className="w-4 h-4" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-xs text-white">الوحدة {p.unit_number}</span>
                              <span className="text-[10px] text-brand-300 bg-brand-950/40 px-2 py-0.5 rounded-full border border-brand-800/40">
                                {p.project_name || 'مشروع مستقل'}
                              </span>
                            </div>
                            <span className="text-[11px] text-slate-400">
                              {p.location} • {p.bedrooms} غرف • {p.area} م²
                            </span>
                          </div>
                        </div>

                        <div className="text-end">
                          <span className="text-xs font-black text-emerald-400 block">
                            {p.total_price.toLocaleString()} {p.currency}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            مقدم: {p.down_payment.toLocaleString()} ج.م
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Price Customization */}
              {selectedProperty && (
                <div className="p-3.5 rounded-2xl bg-slate-800/60 border border-slate-700/60 space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                      <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
                      السعر المقترح في العرض (Custom Offer Price):
                    </label>
                    <span className="text-[10px] text-slate-400">
                      السعر الأصلي: {selectedProperty.total_price.toLocaleString()} ج.م
                    </span>
                  </div>
                  <input
                    type="number"
                    value={customPrice}
                    onChange={(e) => setCustomPrice(e.target.value)}
                    placeholder="السعر المعروض للعميل..."
                    className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs font-bold text-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/40"
                  />
                </div>
              )}
            </div>
          )}

          {step === 'PREVIEW' && messageData && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-2xl bg-emerald-950/20 border border-emerald-500/30 flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-emerald-400 block">
                    تم إنشاء رسالة العرض الذكية بنجاح
                  </span>
                  <p className="text-[11px] text-slate-300">
                    الوحدة: {selectedProperty?.unit_number} بمشروع {selectedProperty?.project_name} • السعر المعروض: {parseFloat(customPrice || '0').toLocaleString()} ج.م
                  </p>
                </div>
                <Sparkles className="w-5 h-5 text-emerald-400" />
              </div>

              {/* Message text area */}
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">
                  نص الرسالة المعدة باللهجة المصرية (يمكنك تعديل الصياغة حسب رغبتك):
                </label>
                <textarea
                  rows={6}
                  value={editedMessage}
                  onChange={(e) => setEditedMessage(e.target.value)}
                  className="w-full bg-slate-800/90 border border-slate-700 rounded-2xl p-3 text-xs text-slate-100 leading-relaxed focus:outline-none focus:ring-2 focus:ring-emerald-500/40 font-sans"
                />
              </div>

              {/* Photos attachment guide */}
              {messageData.property_images && messageData.property_images.length > 0 ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs text-slate-300 font-semibold">
                    <ImageIcon className="w-4 h-4 text-brand-400" />
                    <span>صور الوحدة المتاحة للإرفاق ({messageData.property_images.length} صور):</span>
                  </div>
                  <div className="flex gap-2 overflow-x-auto pb-2">
                    {messageData.property_images.map((imgUrl, i) => (
                      <img
                        key={i}
                        src={imgUrl}
                        alt={`Unit ${i + 1}`}
                        className="w-20 h-20 rounded-xl object-cover border border-slate-700 hover:scale-105 transition-transform"
                      />
                    ))}
                  </div>
                  <p className="text-[10px] text-slate-400 bg-slate-800/50 p-2 rounded-xl border border-slate-800">
                    💡 <strong>تلميح:</strong> بعد النقر على "فتح محادثة واتساب"، ستفتح المحادثة بالنص المكتوب جاهزاً. يمكنك حفظ أو نسخ الصور وإرسالها مباشرة داخل المحادثة.
                  </p>
                </div>
              ) : (
                <p className="text-[11px] text-slate-400">
                  لم يتم رفع صور لهذه الوحدة بعد. سيتم إرسال المواصفات النصية عبر الواتساب.
                </p>
              )}
            </div>
          )}

          {step === 'SENT' && (
            <div className="py-8 text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div>
                <h4 className="text-lg font-black text-white">تم إرسال وتوثيق العرض بنجاح!</h4>
                <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
                  تم تسجيل العرض العقاري رقم #{createdOffer?.id} وحفظ نص الرسالة وتحديث الجدول الزمني للعميل إلى حالة (SHARED).
                </p>
              </div>
            </div>
          )}

        </div>

        {/* Modal Footer Actions */}
        <div className="pt-4 border-t border-slate-800 flex items-center justify-between gap-3">
          {step === 'SELECT' && (
            <>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
              >
                إلغاء
              </button>
              <button
                type="button"
                disabled={!selectedProperty || generating}
                onClick={handleGenerateMessage}
                className="px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 text-white flex items-center gap-1.5 transition-all shadow-md"
              >
                <Sparkles className="w-4 h-4" />
                <span>{generating ? 'جاري تجهيز الرسالة...' : 'التالي: إعداد رسالة الواتساب'}</span>
              </button>
            </>
          )}

          {step === 'PREVIEW' && (
            <>
              <button
                type="button"
                onClick={() => setStep('SELECT')}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
              >
                الرجوع لاختيار وحدة أخرى
              </button>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleOpenWhatsApp}
                  className="px-4 py-2.5 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-emerald-500/40 flex items-center gap-1.5 transition-all"
                >
                  <ExternalLink className="w-4 h-4" />
                  <span>1. فتح واتساب</span>
                </button>
                <button
                  type="button"
                  disabled={confirming}
                  onClick={handleConfirmSent}
                  className="px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white flex items-center gap-1.5 transition-all shadow-lg"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>{confirming ? 'جاري التوثيق...' : '2. تأكيد الإرسال وتوثيق العرض'}</span>
                </button>
              </div>
            </>
          )}

          {step === 'SENT' && (
            <button
              type="button"
              onClick={onClose}
              className="w-full py-2.5 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-white"
            >
              إغلاق
            </button>
          )}
        </div>

      </div>
    </div>
  );
};

