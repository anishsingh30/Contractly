'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useContractly } from '@/context/contractly-context';
import {
  ContractNoteItem,
  fetchContractNotes,
  createContractNote,
  updateContractNote,
  deleteContractNote
} from '@/lib/api-client';
import { Button } from '@/components/ui/button';

interface ContractNotesPanelProps {
  contractId: string;
}

export function ContractNotesPanel({ contractId }: ContractNotesPanelProps) {
  const { currentUser, addToast } = useContractly();

  const [notes, setNotes] = useState<ContractNoteItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // New Note Form
  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newReminderDate, setNewReminderDate] = useState('');
  const [newIsImportant, setNewIsImportant] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Edit State
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editContent, setEditContent] = useState('');
  const [editReminderDate, setEditReminderDate] = useState('');
  const [editIsImportant, setEditIsImportant] = useState(false);

  const loadNotes = useCallback(async () => {
    if (!contractId) return;
    setIsLoading(true);
    try {
      const data = await fetchContractNotes(contractId);
      setNotes(data);
    } catch (err) {
      console.error('Failed to load notes:', err);
    } finally {
      setIsLoading(false);
    }
  }, [contractId]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  const handleCreateNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) {
      addToast('Validation', 'Note content is required.', 'warning');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await createContractNote(contractId, {
        title: newTitle.trim() || undefined,
        content: newContent.trim(),
        reminder_date: newReminderDate || undefined,
        is_important: newIsImportant
      });
      if (res) {
        addToast('Note Added', 'Persistent contract note saved.', 'success');
        setNewTitle('');
        setNewContent('');
        setNewReminderDate('');
        setNewIsImportant(false);
        setIsAdding(false);
        loadNotes();
      }
    } catch (err) {
      addToast('Error', 'Failed to save note.', 'danger');
    } finally {
      setIsSubmitting(false);
    }
  };

  const startEdit = (note: ContractNoteItem) => {
    setEditingNoteId(note.id);
    setEditTitle(note.title || '');
    setEditContent(note.content);
    setEditReminderDate(note.reminder_date || '');
    setEditIsImportant(note.is_important);
  };

  const handleUpdateNote = async (noteId: string) => {
    if (!editContent.trim()) return;
    const res = await updateContractNote(contractId, noteId, {
      title: editTitle.trim() || undefined,
      content: editContent.trim(),
      reminder_date: editReminderDate || undefined,
      is_important: editIsImportant
    });
    if (res) {
      addToast('Note Updated', 'Changes saved successfully.', 'success');
      setEditingNoteId(null);
      loadNotes();
    }
  };

  const handleDelete = async (noteId: string) => {
    if (!window.confirm('Delete this contract note?')) return;
    const ok = await deleteContractNote(contractId, noteId);
    if (ok) {
      addToast('Note Deleted', 'Note removed from agreement.', 'info');
      loadNotes();
    }
  };

  return (
    <div className="space-y-4 bg-[#FCFAF5] border border-[#DED6C8] rounded-[2px] p-4">
      <div className="flex items-center justify-between border-b border-[#DED6C8] pb-3">
        <div>
          <h3 className="font-serif font-bold text-sm text-[#242321]">Contract Notes & Reminders</h3>
          <p className="text-[11px] text-[#6F6A61] mt-0.5">
            Internal legal commentary, follow-up dates, and execution context.
          </p>
        </div>
        {!isAdding && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsAdding(true)}
            className="text-xs"
          >
            + Add Note
          </Button>
        )}
      </div>

      {/* Add Note Form */}
      {isAdding && (
        <form onSubmit={handleCreateNote} className="space-y-3 bg-[#F7F3EA] p-3 rounded-[2px] border border-[#DED6C8] text-xs">
          <div>
            <label className="block text-[10px] font-mono uppercase text-[#6F6A61] mb-1">
              Title (Optional)
            </label>
            <input
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="e.g. Counterparty Insurance Verification"
              className="w-full bg-[#FCFAF5] border border-[#DED6C8] px-2.5 py-1.5 rounded-[2px] text-xs text-[#242321]"
            />
          </div>

          <div>
            <label className="block text-[10px] font-mono uppercase text-[#6F6A61] mb-1">
              Note Content *
            </label>
            <textarea
              required
              rows={3}
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              placeholder="Record legal rationale, negotiation status, or covenant commitments..."
              className="w-full bg-[#FCFAF5] border border-[#DED6C8] p-2 rounded-[2px] text-xs text-[#242321]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-mono uppercase text-[#6F6A61] mb-1">
                Reminder Date (Optional)
              </label>
              <input
                type="date"
                value={newReminderDate}
                onChange={(e) => setNewReminderDate(e.target.value)}
                className="w-full bg-[#FCFAF5] border border-[#DED6C8] px-2 py-1 rounded-[2px] text-xs text-[#242321]"
              />
            </div>
            <div className="flex items-center gap-2 pt-4">
              <input
                type="checkbox"
                id="note-important"
                checked={newIsImportant}
                onChange={(e) => setNewIsImportant(e.target.checked)}
                className="rounded text-[#3F4634]"
              />
              <label htmlFor="note-important" className="text-xs text-[#242321] select-none">
                Mark as Important
              </label>
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsAdding(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Saving...' : 'Save Note'}
            </Button>
          </div>
        </form>
      )}

      {/* Notes List */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="text-center py-6 text-xs text-[#6F6A61]">Loading notes...</div>
        ) : notes.length === 0 ? (
          <div className="text-center py-6 text-xs text-[#6F6A61]">
            No internal notes recorded yet for this contract.
          </div>
        ) : (
          notes.map((n) => (
            <div
              key={n.id}
              className={`p-3 bg-[#FCFAF5] border rounded-[2px] text-xs space-y-2 transition-all ${
                n.is_important ? 'border-l-4 border-l-[#9A6A32] border-[#DED6C8]' : 'border-[#DED6C8]'
              }`}
            >
              {editingNoteId === n.id ? (
                <div className="space-y-2 bg-[#F7F3EA] p-2.5 rounded-[2px]">
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    placeholder="Title"
                    className="w-full bg-[#FCFAF5] border border-[#DED6C8] px-2 py-1 text-xs text-[#242321]"
                  />
                  <textarea
                    rows={2}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="w-full bg-[#FCFAF5] border border-[#DED6C8] p-1.5 text-xs text-[#242321]"
                  />
                  <div className="flex items-center justify-between">
                    <input
                      type="date"
                      value={editReminderDate}
                      onChange={(e) => setEditReminderDate(e.target.value)}
                      className="bg-[#FCFAF5] border border-[#DED6C8] px-2 py-0.5 text-xs text-[#242321]"
                    />
                    <div className="flex items-center gap-2">
                      <Button variant="outline" size="sm" onClick={() => setEditingNoteId(null)}>
                        Cancel
                      </Button>
                      <Button variant="primary" size="sm" onClick={() => handleUpdateNote(n.id)}>
                        Save
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      {n.is_important && (
                        <span className="text-[9px] uppercase px-1.5 py-0.2 bg-[#FEF9EE] border border-[#F7E5C1] text-[#9A6A32] font-mono font-bold rounded-[2px]">
                          Important
                        </span>
                      )}
                      <span className="font-semibold text-xs text-[#242321]">
                        {n.title || 'Contract Note'}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-[11px] text-[#6F6A61]">
                      <span>By <strong>{n.author_name}</strong></span>
                      {currentUser?.id === n.author_user_id && (
                        <>
                          <button
                            onClick={() => startEdit(n)}
                            className="hover:text-[#242321] ml-2 text-[10px]"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleDelete(n.id)}
                            className="hover:text-[#8B3F3F] ml-1 text-[10px]"
                          >
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-[#3A3835] leading-relaxed whitespace-pre-wrap">
                    {n.content}
                  </p>

                  {n.reminder_date && (
                    <div className="pt-1 text-[10px] font-mono text-[#9A6A32]">
                      ⏰ Reminder Scheduled: <strong>{n.reminder_date}</strong>
                    </div>
                  )}
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
