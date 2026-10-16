'use client';

import React from 'react';
import { useContractly } from '@/context/contractly-context';

export function ToastContainer() {
  const { toasts, removeToast } = useContractly();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => {
        let border = 'border-[#DED6C8]';
        let bg = 'bg-[#FCFAF5]';
        let titleColor = 'text-[#242321]';

        if (toast.type === 'success') {
          border = 'border-[#C6D8C6]';
          titleColor = 'text-[#4F6B50]';
        } else if (toast.type === 'warning') {
          border = 'border-[#E5D2B8]';
          titleColor = 'text-[#9A6A32]';
        } else if (toast.type === 'danger') {
          border = 'border-[#E2BDBF]';
          titleColor = 'text-[#8B3F3F]';
        }

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto p-3.5 border ${border} ${bg} shadow-sm rounded-[2px] transition-all`}
            role="status"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className={`text-xs font-semibold ${titleColor}`}>{toast.title}</p>
                <p className="text-xs text-[#6F6A61] mt-0.5 leading-relaxed">{toast.message}</p>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-[#6F6A61] hover:text-[#242321] text-xs font-mono ml-2 p-1"
                aria-label="Close"
              >
                ×
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
