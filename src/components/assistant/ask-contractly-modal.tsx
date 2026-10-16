'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { askContractlyChatBackend } from '@/lib/api-client';

interface AskContractlyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ChatMessage {
  sender: 'user' | 'assistant';
  text: string;
  disclaimer?: string;
}

export function AskContractlyModal({ isOpen, onClose }: AskContractlyModalProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      sender: 'assistant',
      text: 'Welcome to Ask Contractly. I provide educational explanations of contract terminology, lifecycle stages, and Contractly workflows.',
      disclaimer: 'This is an informational explanation and does not constitute legal advice.'
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  if (!isOpen) return null;

  const handleSendMessage = async (queryText?: string) => {
    const textToSend = (queryText || inputValue).trim();
    if (!textToSend || isLoading) return;

    const userMsg: ChatMessage = { sender: 'user', text: textToSend };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      // Build lightweight conversation history for controlled context
      // Exclude initial greeting (index 0) and any prior system notices/errors
      const historyPayload = messages
        .filter((m, idx) => idx > 0 && !m.disclaimer?.includes('System Notice'))
        .slice(-6)
        .map((m) => ({
          role: m.sender,
          content: m.text
        }));

      const res = await askContractlyChatBackend(textToSend, historyPayload);
      if (res && res.reply) {
        setMessages((prev) => [
          ...prev,
          {
            sender: 'assistant',
            text: res.reply,
            disclaimer: res.disclaimer
          }
        ]);
      } else {
        const errorText = res?.error || 'AI service is currently unavailable. Please verify environment configuration.';
        setMessages((prev) => [
          ...prev,
          {
            sender: 'assistant',
            text: errorText,
            disclaimer: 'System Notice: AI request could not be processed.'
          }
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          sender: 'assistant',
          text: 'An unexpected connection error occurred.',
          disclaimer: 'System Notice: Connection failure.'
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-none p-4">
      <div className="bg-[#FCFAF5] border border-[#DED6C8] shadow-lg rounded-[2px] w-full max-w-2xl flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="p-4 border-b border-[#DED6C8] flex items-center justify-between bg-[#F7F3EA]">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-serif font-bold text-base text-[#242321]">
                Ask Contractly
              </h2>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 bg-[#EFECE3] border border-[#DED6C8] text-[#3F4634] font-medium rounded-[2px]">
                General Assistant
              </span>
            </div>
            <p className="text-[11px] text-[#6F6A61] mt-0.5">
              Educational guidance on contract concepts, lifecycle management, and terminology.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-sm font-mono text-[#6F6A61] hover:text-[#242321] px-2 py-1 rounded-[2px]"
          >
            ✕
          </button>
        </div>

        {/* Message Log */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[300px]">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`p-3 rounded-[2px] text-xs leading-relaxed ${
                m.sender === 'user'
                  ? 'bg-[#EFECE3] text-[#242321] ml-8 border border-[#DED6C8]'
                  : 'bg-[#FCFAF5] text-[#242321] mr-8 border border-[#DED6C8]'
              }`}
            >
              <p className="whitespace-pre-wrap">{m.text}</p>
              {m.disclaimer && (
                <div className="mt-2 pt-2 border-t border-[#DED6C8]/60 text-[10px] text-[#8C827A] italic">
                  {m.disclaimer}
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="p-3 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] text-xs text-[#6F6A61] mr-8 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#3F4634] animate-pulse" />
              <span>Formulating educational explanation...</span>
            </div>
          )}
        </div>

        {/* Suggested Queries */}
        <div className="px-4 py-2 bg-[#F7F3EA] border-t border-[#DED6C8]">
          <span className="text-[10px] uppercase font-mono text-[#6F6A61] block mb-1 font-semibold">
            Suggested topics:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {[
              'What is an auto-renewal clause?',
              'Explain limitation of liability super-caps',
              'What is termination for convenience?',
              'How does Contractly approval flow work?'
            ].map((q) => (
              <button
                key={q}
                disabled={isLoading}
                onClick={() => handleSendMessage(q)}
                className="text-[11px] bg-[#FCFAF5] hover:bg-[#EFECE3] disabled:opacity-50 text-[#3F4634] border border-[#DED6C8] px-2 py-0.5 rounded-[2px] transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-[#DED6C8] bg-[#FCFAF5] flex gap-2">
          <input
            type="text"
            value={inputValue}
            disabled={isLoading}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Ask a question about contract management concepts or terminology..."
            className="flex-1 bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] px-3 py-2 rounded-[2px] focus:bg-[#FCFAF5] focus:border-[#3F4634] disabled:opacity-60"
          />
          <Button
            onClick={() => handleSendMessage()}
            disabled={isLoading || !inputValue.trim()}
            variant="primary"
            size="sm"
          >
            {isLoading ? 'Sending...' : 'Ask'}
          </Button>
        </div>
      </div>
    </div>
  );
}
