/**
 * QueryPanel component for asking questions.
 * Presentational component - receives ask/loading/reset from parent.
 */

import { useState, useCallback, useRef, useEffect, type FormEvent, type KeyboardEvent } from 'react';
import { Button, Textarea } from './ui';

interface QueryPanelProps {
  ask: (request: { question: string; top_k?: number }) => Promise<void>;
  loading: boolean;
  reset: () => void;
}

export function QueryPanel({ ask, loading, reset }: QueryPanelProps) {
  const [question, setQuestion] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  const adjustHeight = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [adjustHeight]);

  const validateQuestion = (): string | null => {
    const trimmed = question.trim();
    if (!trimmed) return 'Please enter a question';
    if (trimmed.length > 1000) return 'Question must be 1,000 characters or less';
    return null;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const validation = validateQuestion();
    if (validation) {
      setValidationError(validation);
      return;
    }

    // ask never rejects - it sets error state internally in the hook
    await ask({ question: question.trim(), top_k: 5 });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleClear = () => {
    setQuestion('');
    setValidationError(null);
    reset();
    textareaRef.current?.focus();
  };

  return (
    <section className="card p-5" aria-labelledby="query-heading">
      <h2 id="query-heading" className="text-lg font-semibold text-slate-900 mb-4">
        Ask a Question
      </h2>

      <form onSubmit={handleSubmit} className="space-y-3">
        <Textarea
          ref={textareaRef}
          label="Question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="What did I save about…?"
          aria-describedby="query-hint"
          disabled={loading}
          rows={3}
        />
        <p id="query-hint" className="text-xs text-slate-500">
          Press <kbd className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-700 font-mono text-xs">Ctrl+Enter</kbd> or <kbd className="px-1.5 py-0.5 bg-slate-100 rounded text-slate-700 font-mono text-xs">⌘+Enter</kbd> to ask
        </p>

        {validationError && (
          <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm" role="alert">
            {validationError}
          </div>
        )}

        <div className="flex items-center gap-3 pt-2">
          <Button type="submit" loading={loading} disabled={!question.trim() || loading}>
            Ask
          </Button>
          {question.trim() && !loading && (
            <Button type="button" variant="ghost" onClick={handleClear}>
              Clear
            </Button>
          )}
        </div>
      </form>
    </section>
  );
}