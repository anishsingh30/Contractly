'use client';

import React, { useState, useRef, useEffect } from 'react';

interface HelpTooltipProps {
  text: string;
  className?: string;
  term?: string;
}

export function HelpTooltip({ text, className = '', term }: HelpTooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  return (
    <span
      ref={containerRef}
      className={`relative inline-flex items-center align-middle ml-1 ${className}`}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <button
        type="button"
        aria-label={term ? `Explanation for ${term}` : 'What does this mean?'}
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        className="w-3.5 h-3.5 rounded-full bg-[#EFECE3] border border-[#DED6C8] hover:border-[#3F4634] text-[#6F6A61] hover:text-[#3F4634] flex items-center justify-center text-[10px] font-mono leading-none transition-colors cursor-help focus:outline-none focus:ring-1 focus:ring-[#3F4634]"
      >
        ?
      </button>

      {isOpen && (
        <span
          role="tooltip"
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 w-60 p-2.5 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] shadow-lg text-left text-xs text-[#242321] z-50 pointer-events-none select-none font-sans"
        >
          {term && (
            <span className="block font-semibold text-[11px] text-[#3F4634] border-b border-[#DED6C8]/60 pb-1 mb-1">
              {term}
            </span>
          )}
          <span className="block text-[11px] text-[#6F6A61] leading-relaxed font-normal">
            {text}
          </span>
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-[#DED6C8]" />
        </span>
      )}
    </span>
  );
}
