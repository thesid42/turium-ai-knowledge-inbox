/**
 * ItemRow component for displaying a single item with expandable chunks.
 */

import { useState } from 'react';
import { getItem } from '../api/client';
import type { Item, ItemDetail, Chunk } from '../types';
import { Badge, Button, Spinner, EmptyState } from './ui';

interface ItemRowProps {
  item: Item;
  onDelete: (id: string) => Promise<void>;
}

export function ItemRow({ item, onDelete }: ItemRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [detail, setDetail] = useState<ItemDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDelete = async () => {
    setDeleting(true);
    setDeleteError(null);
    try {
      await onDelete(item.id);
    } catch (err) {
      if (err instanceof Error && 'code' in err) {
        const apiError = err as { message: string };
        setDeleteError(apiError.message);
      } else {
        setDeleteError(err instanceof Error ? err.message : 'Failed to delete item');
      }
    } finally {
      setDeleting(false);
    }
  };

  const toggleExpand = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }

    if (detail) {
      setExpanded(true);
      return;
    }

    setLoadingDetail(true);
    setDetailError(null);
    try {
      const data = await getItem(item.id);
      setDetail(data);
      setExpanded(true);
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Failed to load chunks');
    } finally {
      setLoadingDetail(false);
    }
  };

  const formatDate = (isoString: string): string => {
    try {
      return new Date(isoString).toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  const getTitle = (): string => {
    if (item.title) return item.title;
    if (item.type === 'url' && item.source) {
      try {
        return new URL(item.source).hostname;
      } catch {
        return 'Untitled URL';
      }
    }
    return 'Untitled note';
  };

  const truncate = (text: string, maxLength: number): string => {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength).trimEnd() + '…';
  };

  return (
    <article className="card overflow-hidden">
      <div className="p-4 flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex items-center gap-2 flex-shrink-0">
          <Badge variant={item.type}>{item.type === 'note' ? 'Note' : 'URL'}</Badge>
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-slate-900 truncate">{getTitle()}</h3>
          <div className="flex items-center gap-3 mt-1 text-sm text-slate-500">
            <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
            <span className="flex items-center gap-1">
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {item.chunk_count} chunk{item.chunk_count !== 1 ? 's' : ''}
            </span>
            {item.char_count > 0 && (
              <span>{item.char_count.toLocaleString()} chars</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {item.type === 'url' && item.source && (
            <a
              href={item.source}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost p-2 text-slate-500 hover:text-indigo-600"
              aria-label={`Open source: ${item.source}`}
              title="Open source"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}

          <button
            type="button"
            onClick={toggleExpand}
            disabled={loadingDetail}
            className="btn-ghost p-2 text-slate-500 hover:text-indigo-600"
            aria-expanded={expanded}
            aria-controls={`item-chunks-${item.id}`}
          >
            {loadingDetail ? (
              <Spinner size="sm" />
            ) : (
              <svg className={`w-5 h-5 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            )}
          </button>

          <button
            type="button"
            onClick={() => {
              setDeleteConfirm(true);
              setDeleteError(null);
            }}
            disabled={deleting}
            className="btn-ghost p-2 text-slate-500 hover:text-red-600"
            aria-label={`Delete ${getTitle()}`}
          >
            {deleting ? <Spinner size="sm" /> : (
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {deleteConfirm && (
        <div className="border-t border-slate-200 p-4 bg-slate-50 flex flex-col sm:flex-row sm:items-center sm:justify-end gap-3" role="alertdialog" aria-modal="true" aria-labelledby="delete-confirm-title">
          <p id="delete-confirm-title" className="text-sm text-slate-700">
            Delete "{truncate(getTitle(), 50)}"?
          </p>
          {deleteError && (
            <div className="text-sm text-red-600 flex-1" role="alert">
              {deleteError}
            </div>
          )}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Button variant="ghost" onClick={() => setDeleteConfirm(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleDelete} loading={deleting}>
              Delete
            </Button>
          </div>
        </div>
      )}

      <div
        id={`item-chunks-${item.id}`}
        role="region"
        aria-labelledby={`item-chunks-heading-${item.id}`}
        className={`overflow-hidden transition-all duration-200 ${expanded ? 'max-h-[400px]' : 'max-h-0'}`}
      >
        {expanded && (
          <div className="border-t border-slate-200 bg-slate-50 p-4" id={`item-chunks-heading-${item.id}`}>
            {loadingDetail ? (
              <div className="flex justify-center py-4" aria-busy="true">
                <Spinner />
              </div>
            ) : detailError ? (
              <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm" role="alert">
                <p>{detailError}</p>
                <button
                  type="button"
                  onClick={toggleExpand}
                  className="mt-2 text-xs text-indigo-600 hover:underline"
                >
                  Retry
                </button>
              </div>
            ) : detail ? (
              detail.chunks.length > 0 ? (
                <div className="space-y-3">
                  <h4 className="text-sm font-medium text-slate-700 flex items-center gap-2">
                    <span>{detail.chunks.length} chunk{detail.chunks.length !== 1 ? 's' : ''}</span>
                    <span className="text-slate-400">(model: {detail.chunks[0]?.embedding_model || 'unknown'})</span>
                  </h4>
                  <div className="space-y-2 max-h-60 overflow-y-auto scrollbar-thin">
                    {detail.chunks.map((chunk: Chunk) => (
                      <div key={chunk.id} className="bg-white rounded border border-slate-200 p-3">
                        <div className="flex items-start justify-between gap-2 mb-1">
                          <Badge variant="note">Chunk {chunk.chunk_index + 1}</Badge>
                          <span className="text-xs text-slate-400 font-mono whitespace-nowrap">
                            chars {chunk.char_start}–{chunk.char_end}
                          </span>
                        </div>
                        <pre className="text-xs text-slate-600 font-mono whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
                          {truncate(chunk.content, 500)}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState title="No chunks" description="This item has no content chunks." />
              )
            ) : (
              <EmptyState title="Failed to load chunks" description="Click the expand button to retry." />
            )}
          </div>
        )}
      </div>
    </article>
  );
}