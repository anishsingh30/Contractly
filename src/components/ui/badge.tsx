import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'compliant' | 'warning' | 'danger' | 'neutral' | 'olive';
  className?: string;
}

export function Badge({ children, variant = 'neutral', className = '' }: BadgeProps) {
  let styles = 'bg-[#EFECE3] text-[#242321] border-[#DED6C8]';

  if (variant === 'compliant') {
    styles = 'bg-[#EDF2EC] text-[#4F6B50] border-[#C6D8C6]';
  } else if (variant === 'warning') {
    styles = 'bg-[#F7EFE4] text-[#9A6A32] border-[#E5D2B8]';
  } else if (variant === 'danger') {
    styles = 'bg-[#F7EDED] text-[#8B3F3F] border-[#E2BDBF]';
  } else if (variant === 'olive') {
    styles = 'bg-[#EEF1EB] text-[#3F4634] border-[#D1D8CA]';
  }

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium border rounded-[2px] tracking-normal ${styles} ${className}`}
    >
      {children}
    </span>
  );
}
