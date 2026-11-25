import React, { useEffect, useState } from 'react';
import { 
  Image as ImageIcon, Upload, Trash2, Star, CheckCircle2, 
  AlertCircle, X, Plus, Eye 
} from 'lucide-react';
import { api } from '../../api/client';
import { Property, PropertyImage } from '../../types';
import { useAuth } from '../../context/AuthContext';

interface PropertyImagesModalProps {
  isOpen: boolean;
  onClose: () => void;
  property: Property | null;
  onImagesUpdated?: () => void;
}

export const PropertyImagesModal: React.FC<PropertyImagesModalProps> = ({
  isOpen,
  onClose,
  property,
  onImagesUpdated,
}) => {
  const [images, setImages] = useState<PropertyImage[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [caption, setCaption] = useState('');
  const [isPrimary, setIsPrimary] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const { user } = useAuth();

  const isManager = ['SUPER_ADMIN', 'COMPANY_ADMIN', 'SALES_MANAGER'].includes(user?.role || '');

  useEffect(() => {
    if (isOpen && property) {
      loadImages();
      setSelectedFile(null);
      setFilePreview(null);
      setCaption('');
      setIsPrimary(false);
      setError('');
      setSuccessMsg('');
    }
  }, [isOpen, property]);

  const loadImages = () => {
    if (!property) return;
    setLoading(true);
    api.get<PropertyImage[]>(`/properties/${property.id}/images`)
      .then(setImages)
      .catch((err) => setError(err.message || 'فشل تحميل صور الوحدة'))
      .finally(() => setLoading(false));
  };

  if (!isOpen || !property) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setFilePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !property) return;

    setUploading(true);
    setError('');
    setSuccessMsg('');

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      if (caption.trim()) formData.append('caption', caption.trim());
      formData.append('is_primary', String(isPrimary));

      await api.postForm(`/properties/${property.id}/images`, formData);
      setSuccessMsg('تم رفع الصورة بنجاح');
      setSelectedFile(null);
      setFilePreview(null);
      setCaption('');
      setIsPrimary(false);
      loadImages();
      if (onImagesUpdated) onImagesUpdated();
    } catch (err: any) {
      setError(err.message || 'فشل رفع الصورة');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteImage = async (imageId: number) => {
    if (!window.confirm('هل أنت متأكد من رغبتك في حذف هذه الصورة؟')) return;
    try {
      await api.delete(`/properties/${property.id}/images/${imageId}`);
      setSuccessMsg('تم حذف الصورة بنجاح');
      loadImages();
      if (onImagesUpdated) onImagesUpdated();
    } catch (err: any) {
      setError(err.message || 'فشل حذف الصورة');
    }
  };

  const handleSetPrimary = async (imageId: number) => {
    try {
      await api.put(`/properties/${property.id}/images/${imageId}/primary`);
      setSuccessMsg('تم تعيين الصورة كصورة رئيسية');
      loadImages();
      if (onImagesUpdated) onImagesUpdated();
    } catch (err: any) {
      setError(err.message || 'فشل تعيين الصورة كصورة رئيسية');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl max-w-3xl w-full p-6 shadow-2xl relative text-start flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-brand-500/20 border border-brand-500/30 flex items-center justify-center text-brand-400">
              <ImageIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-white">معرض صور الوحدة العقارية</h3>
              <p className="text-xs text-slate-400">
                الوحدة {property.unit_number} - {property.project_name || 'مشروع مستقل'} ({property.location})
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

        {successMsg && (
          <div className="my-3 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto py-4 space-y-6">

          {/* Upload Section for Managers */}
          {isManager && (
            <div className="p-4 rounded-2xl bg-slate-800/40 border border-slate-800 space-y-3">
              <h4 className="text-xs font-bold text-white flex items-center gap-1.5">
                <Upload className="w-3.5 h-3.5 text-brand-400" />
                رفع صورة جديدة للوحدة
              </h4>

              <form onSubmit={handleUpload} className="space-y-3 text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-center">
                  <div>
                    <label className="block text-slate-400 mb-1">اختر ملف الصورة (.jpg, .jpeg, .png, .webp):</label>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleFileChange}
                      className="w-full text-xs text-slate-400 file:mr-2 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-brand-600 file:text-white hover:file:bg-brand-500 cursor-pointer"
                    />
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1">وصف أو تعليق على الصورة (اختياري):</label>
                    <input
                      type="text"
                      value={caption}
                      onChange={(e) => setCaption(e.target.value)}
                      placeholder="مثال: إطلالة الريسبشن، المطبخ، فيو البحيرة..."
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500"
                    />
                  </div>
                </div>

                {filePreview && (
                  <div className="flex items-center gap-3 p-2 bg-slate-900/60 rounded-xl border border-slate-700">
                    <img src={filePreview} alt="Preview" className="w-16 h-16 rounded-lg object-cover" />
                    <div className="flex items-center gap-4 text-xs">
                      <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isPrimary}
                          onChange={(e) => setIsPrimary(e.target.checked)}
                          className="rounded text-brand-600 focus:ring-brand-500"
                        />
                        <span>تعيين كصورة رئيسية للوحدة</span>
                      </label>
                    </div>
                  </div>
                )}

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={!selectedFile || uploading}
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-brand-600 hover:bg-brand-500 disabled:opacity-40 text-white flex items-center gap-1.5 transition-all shadow-md"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>{uploading ? 'جاري الرفع...' : 'رفع الصورة للمخزون'}</span>
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Images Grid */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-300">
                الصور المسجلة ({images.length})
              </h4>
              <span className="text-[11px] text-slate-400">
                الصورة المميزة بـ ★ تظهر في بطاقة الوحدة ورسائل الواتساب
              </span>
            </div>

            {loading ? (
              <div className="py-12 text-center text-xs text-slate-400 animate-pulse">
                جاري تحميل الصور...
              </div>
            ) : images.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-400 bg-slate-800/20 rounded-2xl border border-slate-800">
                لا توجد صور مرفوعة لهذه الوحدة حتى الآن.
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                {images.map((img) => (
                  <div
                    key={img.id}
                    className={`rounded-2xl overflow-hidden border bg-slate-800/40 relative group transition-all ${
                      img.is_primary ? 'border-amber-500/60 ring-2 ring-amber-500/20' : 'border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    <div className="aspect-video relative overflow-hidden bg-slate-950">
                      <img
                        src={img.image_url}
                        alt={img.caption || 'Property'}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      />
                      {img.is_primary && (
                        <span className="absolute top-2 start-2 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500 text-slate-950 flex items-center gap-1 shadow-md">
                          <Star className="w-3 h-3 fill-current" />
                          رئيسية
                        </span>
                      )}
                    </div>

                    <div className="p-2.5 text-xs space-y-1.5">
                      <p className="text-[11px] text-slate-300 truncate" title={img.caption || ''}>
                        {img.caption || 'صورة بدون وصف'}
                      </p>

                      {isManager && (
                        <div className="flex items-center justify-between pt-1 border-t border-slate-800">
                          {!img.is_primary ? (
                            <button
                              type="button"
                              onClick={() => handleSetPrimary(img.id)}
                              className="text-[10px] text-amber-400 hover:text-amber-300 flex items-center gap-0.5"
                            >
                              <Star className="w-3 h-3" />
                              <span>تعيين كرئيسية</span>
                            </button>
                          ) : (
                            <span className="text-[10px] text-emerald-400 font-semibold">الصورة الأساسية</span>
                          )}

                          <button
                            type="button"
                            onClick={() => handleDeleteImage(img.id)}
                            className="p-1 rounded text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors"
                            title="حذف الصورة"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>

        {/* Footer */}
        <div className="pt-4 border-t border-slate-800 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-white"
          >
            إغلاق
          </button>
        </div>

      </div>
    </div>
  );
};

