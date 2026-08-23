import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { useId } from "react";

import { cn } from "@/helpers/cn";

const CONTROL_CLASSES =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 " +
  "placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 " +
  "focus:ring-brand-100 disabled:bg-slate-50 aria-[invalid=true]:border-red-500";

interface FieldShellProps {
  label: string;
  htmlFor: string;
  error?: string;
  hint?: ReactNode;
  required?: boolean;
  children: ReactNode;
}

function FieldShell({ label, htmlFor, error, hint, required, children }: FieldShellProps) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-800">
        {label}
        {required && <span className="ml-0.5 text-red-600">*</span>}
      </label>
      {children}
      {/* El hint se oculta cuando hay error para no competir por la atencion. */}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : (
        hint && <p className="text-sm text-slate-500">{hint}</p>
      )}
    </div>
  );
}

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  label: string;
  error?: string;
  hint?: ReactNode;
}

export function TextField({ label, error, hint, className, required, ...rest }: TextFieldProps) {
  const id = useId();
  return (
    <FieldShell label={label} htmlFor={id} error={error} hint={hint} required={required}>
      <input
        {...rest}
        id={id}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={cn(CONTROL_CLASSES, className)}
      />
    </FieldShell>
  );
}

export interface TextAreaFieldProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> {
  label: string;
  error?: string;
  hint?: ReactNode;
}

export function TextAreaField({
  label,
  error,
  hint,
  className,
  required,
  ...rest
}: TextAreaFieldProps) {
  const id = useId();
  return (
    <FieldShell label={label} htmlFor={id} error={error} hint={hint} required={required}>
      <textarea
        {...rest}
        id={id}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={cn(CONTROL_CLASSES, "min-h-32 resize-y", className)}
      />
    </FieldShell>
  );
}

export interface SelectFieldProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  label: string;
  error?: string;
  hint?: ReactNode;
}

export function SelectField({
  label,
  error,
  hint,
  className,
  required,
  children,
  ...rest
}: SelectFieldProps) {
  const id = useId();
  return (
    <FieldShell label={label} htmlFor={id} error={error} hint={hint} required={required}>
      <select
        {...rest}
        id={id}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={cn(CONTROL_CLASSES, className)}
      >
        {children}
      </select>
    </FieldShell>
  );
}

export interface CheckboxFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "type"> {
  label: ReactNode;
  error?: string;
}

export function CheckboxField({ label, error, className, ...rest }: CheckboxFieldProps) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <div className="flex items-start gap-3">
        <input
          {...rest}
          type="checkbox"
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
          className={cn(
            "mt-0.5 size-5 shrink-0 rounded border-slate-300 text-brand-600",
            "focus:ring-2 focus:ring-brand-200",
            error && "border-red-500",
            className,
          )}
        />
        <label htmlFor={id} className="text-sm leading-relaxed text-slate-700">
          {label}
        </label>
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
