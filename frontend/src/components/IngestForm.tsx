/**
 * IngestForm component for adding notes and URLs.
 */

import { useState, type FormEvent } from 'react';
import type { IngestRequest } from '../types';
import { Button, Textarea, Input, ErrorBanner, SuccessBanner } from './ui';

type IngestMode = 'note' | 'url';

interface IngestFormProps {
  onIngest: (request: IngestRequest) => Promise<{ chunks_created: number }>;
}

export function IngestForm({ onIngest }: IngestFormProps) {
  const [mode, setMode] = useState<IngestMode>('note');
  const [noteContent, setNoteContent] = useState('');
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const validateNote = (): string | null => {
    const trimmed = noteContent.trim();
    if (!trimmed) return 'Note content cannot be empty';
    if (trimmed.length > 100000) return 'Note content exceeds 100,000 characters';
    return null;
  };

  const validateUrl = (): string | null => {
    const trimmed = url.trim();
    if (!trimmed) return 'URL cannot be empty';
    try {
      const parsed = new URL(trimmed);
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return 'URL must use http:// or https://';
      }
    } catch {
      return 'Please enter a valid URL';
    }
    return null;
  };

  const validateTitle = (): string | null => {
    const trimmed = title.trim();
    if (trimmed.length > 200) return 'Title must be 200 characters or less';
    return null;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const titleValidation = validateTitle();
    if (titleValidation) {
      setError(titleValidation);
      return;
    }

    if (mode === 'note') {
      const noteValidation = validateNote();
      if (noteValidation) {
        setError(noteValidation);
        return;
      }
    } else {
      const urlValidation = validateUrl();
      if (urlValidation) {
        setError(urlValidation);
        return;
      }
    }

    setSubmitting(true);

    try {
      const request: IngestRequest =
        mode === 'note'
          ? { type: 'note', content: noteContent.trim(), title: title.trim() || undefined }
          : { type: 'url', url: url.trim(), title: title.trim() || undefined };

      const response = await onIngest(request);
      setSuccess(`Saved! Created ${response.chunks_created} chunk${response.chunks_created !== 1 ? 's' : ''}.`);
      // Reset form
      setNoteContent('');
      setUrl('');
      setTitle('');
    } catch (err) {
      if (err instanceof Error && 'code' in err) {
        const apiError = err as { code: string; message: string; details?: Record<string, unknown> };
        let message = apiError.message;
        if (apiError.code === 'DUPLICATE_ITEM' && apiError.details?.item_id) {
          message = `This content already exists (item ${apiError.details.item_id})`;
        }
        setError(message);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to save item');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="card p-5" aria-labelledby="ingest-heading">
      <div className="flex items-center justify-between mb-4">
        <h2 id="ingest-heading" className="text-lg font-semibold text-slate-900">
          Add Content
        </h2>
        <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1" role="radiogroup" aria-label="Content type">
          <button
            type="button"
            role="radio"
            aria-checked={mode === 'note'}
            onClick={() => setMode('note')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              mode === 'note' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Note
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={mode === 'url'}
            onClick={() => setMode('url')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              mode === 'url' ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            URL
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === 'note' ? (
          <Textarea
            label="Content"
            value={noteContent}
            onChange={(e) => setNoteContent(e.target.value)}
            placeholder="Paste or type your note here..."
            aria-describedby="note-hint"
            disabled={submitting}
            rows={6}
          />
        ) : (
          <>
            <Input
              label="URL"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/article"
              aria-describedby="url-hint"
              disabled={submitting}
              autoComplete="url"
            />
            <p id="url-hint" className="text-xs text-slate-500">
              The page will be fetched server-side. Private IPs and localhost are blocked.
            </p>
          </>
        )}

        <Input
          label="Title (optional)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={mode === 'note' ? 'Optional title for your note' : 'Optional override title'}
          maxLength={200}
          disabled={submitting}
        />

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
        {success && <SuccessBanner message={success} />}

        <div className="flex items-center gap-3 pt-2">
          <Button type="submit" loading={submitting} disabled={submitting}>
            {mode === 'note' ? 'Save Note' : 'Fetch & Save URL'}
          </Button>
          {submitting && (
            <span className="text-sm text-slate-500" aria-live="polite">
              Processing...
            </span>
          )}
        </div>
      </form>
    </section>
  );
}