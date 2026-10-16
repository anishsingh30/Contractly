'use client';

import React, { useState } from 'react';
import { useContractly } from '@/context/contractly-context';
import { Button } from '@/components/ui/button';
import { FileText } from 'lucide-react';

interface RequestModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type UploadStep = 'idle' | 'uploading' | 'reading' | 'analyzing' | 'checking' | 'ready' | 'error';

export function RequestModal({ isOpen, onClose }: RequestModalProps) {
  const { addNewContract } = useContractly();

  const [title, setTitle] = useState('');
  const [contractType, setContractType] = useState('Master Services Agreement');
  const [counterparty, setCounterparty] = useState('');
  const [department, setDepartment] = useState('General');
  const [value, setValue] = useState('');
  const [startDate, setStartDate] = useState('2026-11-01');
  const [expiryDate, setExpiryDate] = useState('2027-10-31');
  const [notes, setNotes] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadStep, setUploadStep] = useState<UploadStep>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [technicalDetails, setTechnicalDetails] = useState('');
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  if (!isOpen) return null;

  const handleFile = (file: File) => {
    setSelectedFile(file);
    if (!title) {
      setTitle(file.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' '));
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    setUploadStep('uploading');
    setErrorMessage('');

    const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

    try {
      // 1. Initiate backend upload & contract intelligence analysis
      const uploadPromise = addNewContract(
        {
          title,
          contractType,
          counterparty: counterparty.trim() || 'Other Party',
          department,
          value: parseFloat(value) || 0,
          startDate,
          expiryDate,
          renewalDate: expiryDate,
          owner: 'Current User'
        },
        selectedFile || undefined
      );

      // 2. Fast, responsive step transitions (~120-150ms per stage)
      await delay(120);
      setUploadStep('reading');
      await delay(150);
      setUploadStep('analyzing');
      await delay(150);
      setUploadStep('checking');

      // 3. Await backend response
      const uploaded = await uploadPromise;
      if (!uploaded) {
        throw new Error('Upload was not completed. Please try again.');
      }

      // 4. Swift transition to ready
      await delay(100);
      setUploadStep('ready');
    } catch (err: any) {
      setUploadStep('error');
      setErrorMessage("We couldn't upload this file. Please check that it is a PDF, Word document, or text file and try again.");
      setTechnicalDetails(err?.message || 'Network or parser error');
    }
  };

  const handleFinish = () => {
    setUploadStep('idle');
    setSelectedFile(null);
    setTitle('');
    setCounterparty('');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#242321]/45 flex items-center justify-center p-4">
      <div className="bg-[#FCFAF5] border border-[#DED6C8] max-w-lg w-full p-6 rounded-[2px] space-y-4 shadow-md max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#DED6C8] pb-3">
          <div>
            <h2 className="font-serif font-bold text-base text-[#242321]">
              Upload a contract
            </h2>
            <p className="text-xs text-[#6F6A61] mt-0.5">
              Upload a PDF, Word document, or text file. Contractly will read it and help you understand the important parts.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-[#6F6A61] hover:text-[#242321] text-sm font-mono p-1"
          >
            ✕
          </button>
        </div>

        {/* Upload Process States (Instruction 11) */}
        {uploadStep === 'ready' ? (
          <div className="py-8 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-[#EDF2EC] text-[#2E5230] border border-[#C6D8C6] flex items-center justify-center mx-auto text-xl font-bold">
              ✓
            </div>
            <div>
              <h3 className="font-serif font-bold text-base text-[#242321]">
                Your contract is ready
              </h3>
              <p className="text-xs text-[#6F6A61] mt-1 max-w-xs mx-auto">
                We have read your contract, highlighted important terms, and checked for potential concerns.
              </p>
            </div>
            <Button onClick={handleFinish} variant="primary" size="lg" className="w-full text-xs">
              View Contract →
            </Button>
          </div>
        ) : uploadStep !== 'idle' && uploadStep !== 'error' ? (
          <div className="py-8 text-center space-y-5">
            <div className="w-10 h-10 border-2 border-[#3F4634] border-t-transparent rounded-full animate-spin mx-auto" />
            <div className="space-y-1.5">
              <h3 className="font-serif font-bold text-sm text-[#242321]">
                {uploadStep === 'uploading' && 'Uploading...'}
                {uploadStep === 'reading' && 'Reading your contract...'}
                {uploadStep === 'analyzing' && 'Finding important terms...'}
                {uploadStep === 'checking' && 'Checking for potential concerns...'}
              </h3>
              <p className="text-xs text-[#6F6A61]">
                This will only take a few moments.
              </p>
            </div>

            {/* Quick 4-step progress tracker */}
            <div className="flex items-center justify-center gap-2 pt-1 max-w-xs mx-auto">
              {[
                { key: 'uploading', label: 'Upload' },
                { key: 'reading', label: 'Read' },
                { key: 'analyzing', label: 'Analyze' },
                { key: 'checking', label: 'Check' }
              ].map((step, idx) => {
                const stepKeys = ['uploading', 'reading', 'analyzing', 'checking'];
                const currentIdx = stepKeys.indexOf(uploadStep);
                const isPassed = currentIdx > idx;
                const isCurrent = currentIdx === idx;
                return (
                  <div key={step.key} className="flex-1 text-center">
                    <div
                      className={`h-1.5 rounded-full transition-all duration-200 ${
                        isPassed
                          ? 'bg-[#2E5230]'
                          : isCurrent
                          ? 'bg-[#3F4634] animate-pulse'
                          : 'bg-[#DED6C8]'
                      }`}
                    />
                    <span className="text-[10px] text-[#6F6A61] mt-1 block">
                      {step.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 text-xs">
            {/* Error Message Box (Instruction 22) */}
            {uploadStep === 'error' && (
              <div className="p-3 bg-[#F7EDED] border border-[#E2BDBF] rounded-[2px] text-xs text-[#8B3F3F] space-y-2">
                <p className="font-medium">{errorMessage}</p>
                {technicalDetails && (
                  <div>
                    <button
                      type="button"
                      onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                      className="text-[11px] underline text-[#8B3F3F] hover:text-[#242321]"
                    >
                      {showTechnicalDetails ? 'Hide technical details' : 'Technical details'}
                    </button>
                    {showTechnicalDetails && (
                      <p className="font-mono text-[10px] mt-1 p-2 bg-[#FCFAF5] border border-[#E2BDBF] rounded-[2px]">
                        {technicalDetails}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Large Drag & Drop Upload Area (Instruction 11) */}
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              className={`p-6 border-2 border-dashed rounded-[2px] text-center transition-colors ${
                isDragOver
                  ? 'border-[#3F4634] bg-[#F7F3EA]'
                  : selectedFile
                  ? 'border-[#4F6B50] bg-[#EDF2EC]/40'
                  : 'border-[#DED6C8] bg-[#F7F3EA]/60 hover:bg-[#F7F3EA]'
              }`}
            >
              {selectedFile ? (
                <div className="space-y-1">
                  <FileText className="w-5 h-5 mx-auto text-[#3F4634]" />
                  <p className="font-medium text-[#242321]">{selectedFile.name}</p>
                  <p className="text-[11px] text-[#6F6A61]">
                    {(selectedFile.size / 1024).toFixed(1)} KB • Ready to upload
                  </p>
                  <button
                    type="button"
                    onClick={() => setSelectedFile(null)}
                    className="text-[11px] text-[#8B3F3F] hover:underline block mx-auto mt-1"
                  >
                    Remove file
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-[#242321]">
                    Drag your file here
                  </p>
                  <p className="text-xs text-[#6F6A61]">or</p>
                  <label className="inline-block px-3 py-1.5 bg-[#FCFAF5] border border-[#DED6C8] hover:border-[#3F4634] text-[#242321] rounded-[2px] cursor-pointer font-medium text-xs transition-colors">
                    Choose a file
                    <input
                      type="file"
                      accept=".pdf,.docx,.txt"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          handleFile(e.target.files[0]);
                        }
                      }}
                      className="hidden"
                    />
                  </label>
                  <p className="text-[11px] text-[#6F6A61] pt-1">
                    Supported files: PDF, DOCX, TXT
                  </p>
                </div>
              )}
            </div>

            {/* Contract Title */}
            <div>
              <label className="block font-medium text-[#242321] mb-1">
                Contract Name *
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Office Lease Agreement, Cloud Services Contract"
                className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] p-2 rounded-[2px] focus:bg-[#FCFAF5] focus:border-[#3F4634]"
              />
            </div>

            {/* Other Party & Type */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-medium text-[#242321] mb-1">
                  Other Party (Company or Person)
                </label>
                <input
                  type="text"
                  value={counterparty}
                  onChange={(e) => setCounterparty(e.target.value)}
                  placeholder="e.g. CloudStack Systems"
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] p-2 rounded-[2px] focus:bg-[#FCFAF5] focus:border-[#3F4634]"
                />
              </div>

              <div>
                <label className="block font-medium text-[#242321] mb-1">
                  Contract Type
                </label>
                <select
                  value={contractType}
                  onChange={(e) => setContractType(e.target.value)}
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] p-2 rounded-[2px]"
                >
                  <option value="Master Services Agreement">Services Agreement</option>
                  <option value="Non-Disclosure Agreement">Confidentiality (NDA)</option>
                  <option value="Commercial Lease Agreement">Lease Agreement</option>
                  <option value="Employment Agreement">Employment Contract</option>
                  <option value="Software License Agreement">Software License</option>
                  <option value="Consulting Agreement">Consulting / Freelance</option>
                </select>
              </div>
            </div>

            {/* Dates */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-medium text-[#242321] mb-1">Start Date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] p-2 rounded-[2px]"
                />
              </div>
              <div>
                <label className="block font-medium text-[#242321] mb-1">End Date</label>
                <input
                  type="date"
                  value={expiryDate}
                  onChange={(e) => setExpiryDate(e.target.value)}
                  className="w-full bg-[#F7F3EA] border border-[#DED6C8] text-xs text-[#242321] p-2 rounded-[2px]"
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center justify-end gap-2 pt-3 border-t border-[#DED6C8]">
              <Button onClick={onClose} variant="secondary" size="sm" type="button">
                Cancel
              </Button>
              <Button variant="primary" size="sm" type="submit">
                Upload & Understand Contract →
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
