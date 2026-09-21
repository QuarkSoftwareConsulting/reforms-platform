import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";
import { useId } from "react";

import { cn } from "@/helpers/cn";

const CONTROL_CLASSES =
  "w-full rounded-control border-[1.5px] border-line bg-surface px-3.5 py-[13px] text-[15px] " +
  "text-ink placeholder:text-disabled-soft transition-colors " +
  "focus:border-brand focus:outline-none focus:shadow-focus " +
  "disabled:bg-page disabled:text-disabled " +
  "aria-[invalid=true]:border-danger aria-[invalid=true]:bg-danger-bg";

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
      <label htmlFor={htmlFor} className="block text-[15px] font-semibold text-ink">
        {label}
        {required && <span className="ml-0.5 text-danger">*</span>}
      </label>
      {children}
      {/* La ayuda va bajo el campo, nunca dentro del placeholder, y se oculta
          cuando hay error para no competir por la atencion. */}
      {error ? (
        <p id={`${htmlFor}-error`} role="alert" className="text-help font-medium text-danger">
          {error}
        </p>
      ) : (
        hint && <p className="text-help text-muted">{hint}</p>
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

export interface CheckboxFieldProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "type"> {
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
          // `accent-color` deja que el navegador pinte la marca con el azul de
          // marca conservando su propio control nativo, que es el accesible.
          className={cn(
            "mt-0.5 size-5 shrink-0 cursor-pointer rounded accent-brand",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
            "focus-visible:ring-offset-2",
            className,
          )}
        />
        <label htmlFor={id} className="cursor-pointer text-[14.5px] leading-relaxed text-ink">
          {label}
        </label>
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="text-help font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
