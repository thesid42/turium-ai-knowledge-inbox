/**
 * Small shared UI primitives.
 */

import { forwardRef, type ButtonHTMLAttributes, type HTMLAttributes, type ReactNode } from 'react';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'note' | 'url' | 'default';
  children: ReactNode;
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = 'default', className = '', children, ...props }, ref) => {
    const baseClasses = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium';
    const variantClasses =
      variant === 'note'
        ? 'bg-indigo-100 text-indigo-700'
        : variant === 'url'
        ? 'bg-slate-100 text-slate-700'
        : 'bg-slate-100 text-slate-700';

    return (
      <span ref={ref} className={`${baseClasses} ${variantClasses} ${className}`} {...props}>
        {children}
      </span>
    );
  }
);
Badge.displayName = 'Badge';

export interface SpinnerProps extends HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg';
}

export const Spinner = forwardRef<HTMLDivElement, SpinnerProps>(
  ({ size = 'md', className = '', ...props }, ref) => {
    const sizeClasses = size === 'sm' ? 'w-3 h-3 border-[1.5px]' : size === 'lg' ? 'w-6 h-6 border-3' : 'w-4 h-4 border-2';

    return (
      <div
        ref={ref}
        className={`${sizeClasses} border-slate-200 border-t-indigo-600 rounded-full animate-spin ${className}`}
        role="status"
        aria-label="Loading"
        {...props}
      >
        <span className="sr-only">Loading...</span>
      </div>
    );
  }
);
Spinner.displayName = 'Spinner';

export interface ErrorBannerProps extends HTMLAttributes<HTMLDivElement> {
  message: string;
  onDismiss?: () => void;
}

export const ErrorBanner = forwardRef<HTMLDivElement, ErrorBannerProps>(
  ({ message, onDismiss, className = '', ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm flex items-start gap-2 ${className}`}
        role="alert"
        {...props}
      >
        <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
        <div className="flex-1">{message}</div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="text-red-500 hover:text-red-700 font-bold leading-none px-2"
            aria-label="Dismiss error"
          >
            ×
          </button>
        )}
      </div>
    );
  }
);
ErrorBanner.displayName = 'ErrorBanner';

export interface SuccessBannerProps extends HTMLAttributes<HTMLDivElement> {
  message: string;
}

export const SuccessBanner = forwardRef<HTMLDivElement, SuccessBannerProps>(
  ({ message, className = '', ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`p-3 rounded-lg bg-green-50 border border-green-200 text-green-700 text-sm ${className}`}
        role="status"
        {...props}
      >
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
          <span>{message}</span>
        </div>
      </div>
    );
  }
);
SuccessBanner.displayName = 'SuccessBanner';

export interface WarningBannerProps extends HTMLAttributes<HTMLDivElement> {
  message: string;
}

export const WarningBanner = forwardRef<HTMLDivElement, WarningBannerProps>(
  ({ message, className = '', ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm ${className}`}
        role="alert"
        {...props}
      >
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          <span>{message}</span>
        </div>
      </div>
    );
  }
);
WarningBanner.displayName = 'WarningBanner';

export interface EmptyStateProps extends HTMLAttributes<HTMLDivElement> {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export const EmptyState = forwardRef<HTMLDivElement, EmptyStateProps>(
  ({ icon, title, description, action, className = '', ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`text-center py-10 text-slate-500 ${className}`}
        {...props}
      >
        {icon && <div className="mx-auto mb-4 text-slate-300">{icon}</div>}
        <h3 className="text-lg font-medium text-slate-700 mb-1">{title}</h3>
        {description && <p className="text-sm mb-4">{description}</p>}
        {action && <div className="mt-4">{action}</div>}
      </div>
    );
  }
);
EmptyState.displayName = 'EmptyState';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  loading?: boolean;
  children: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', loading = false, disabled, className = '', children, ...props }, ref) => {
    const variantClasses =
      variant === 'primary'
        ? 'bg-indigo-600 text-white hover:bg-indigo-700 focus:ring-indigo-500'
        : variant === 'secondary'
        ? 'bg-slate-100 text-slate-700 hover:bg-slate-200 focus:ring-slate-500'
        : variant === 'danger'
        ? 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500'
        : 'bg-transparent text-slate-600 hover:bg-slate-100 focus:ring-slate-500';

    const baseClasses = 'inline-flex items-center justify-center px-4 py-2 rounded-lg font-medium text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

    return (
      <button
        ref={ref}
        className={`${baseClasses} ${variantClasses} ${className}`}
        disabled={disabled || loading}
        {...props}
      >
        {loading && <Spinner size="sm" className="mr-2" />}
        {children}
      </button>
    );
  }
);
Button.displayName = 'Button';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className = '', id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
    const errorId = error ? `${inputId}-error` : undefined;
    const helperId = helperText ? `${inputId}-helper` : undefined;

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-slate-700 mb-1">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`w-full px-3 py-2 border rounded-lg text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-offset-0 transition-colors disabled:bg-slate-50 disabled:cursor-not-allowed ${
            error
              ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
              : 'border-slate-300 focus:ring-indigo-500 focus:border-transparent'
          } ${className}`}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          {...props}
        />
        {error && (
          <p id={errorId} className="mt-1 text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
        {helperText && !error && (
          <p id={helperId} className="mt-1 text-sm text-slate-500">
            {helperText}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = 'Input';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, helperText, className = '', id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');
    const errorId = error ? `${inputId}-error` : undefined;
    const helperId = helperText ? `${inputId}-helper` : undefined;

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-slate-700 mb-1">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={inputId}
          className={`w-full px-3 py-2 border rounded-lg text-sm placeholder-slate-400 font-mono resize-y min-h-[100px] focus:outline-none focus:ring-2 focus:ring-offset-0 transition-colors disabled:bg-slate-50 disabled:cursor-not-allowed ${
            error
              ? 'border-red-300 focus:ring-red-500 focus:border-red-500'
              : 'border-slate-300 focus:ring-indigo-500 focus:border-transparent'
          } ${className}`}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          {...props}
        />
        {error && (
          <p id={errorId} className="mt-1 text-sm text-red-600" role="alert">
            {error}
          </p>
        )}
        {helperText && !error && (
          <p id={helperId} className="mt-1 text-sm text-slate-500">
            {helperText}
          </p>
        )}
      </div>
    );
  }
);
Textarea.displayName = 'Textarea';