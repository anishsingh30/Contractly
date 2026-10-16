import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...props
}: ButtonProps) {
  const base =
    'inline-flex items-center justify-center font-medium rounded-[2px] transition-colors focus-visible:outline-2 focus-visible:outline-[#3F4634] focus-visible:outline-offset-1 disabled:opacity-50 disabled:cursor-not-allowed';

  const sizeClasses = {
    sm: 'text-xs px-2.5 py-1.5 gap-1.5',
    md: 'text-sm px-3.5 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  }[size];

  const variantClasses = {
    primary: 'bg-[#3F4634] text-[#FCFAF5] hover:bg-[#59604A] border border-[#3F4634]',
    secondary: 'bg-[#FCFAF5] text-[#242321] hover:bg-[#F7F3EA] border border-[#DED6C8]',
    outline: 'bg-transparent text-[#3F4634] hover:bg-[#F7F3EA] border border-[#3F4634]',
    danger: 'bg-[#8B3F3F] text-[#FCFAF5] hover:bg-[#733333] border border-[#8B3F3F]',
    ghost: 'bg-transparent text-[#242321] hover:bg-[#EFECE3] border border-transparent',
  }[variant];

  return (
    <button className={`${base} ${sizeClasses} ${variantClasses} ${className}`} {...props}>
      {children}
    </button>
  );
}
