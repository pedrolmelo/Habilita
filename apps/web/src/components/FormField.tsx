import './FormField.css'
import { useId, type InputHTMLAttributes } from 'react'

type FormFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  id?: string
  label: string
  hint?: string
  error?: string
}

export function FormField({
  id,
  label,
  hint,
  error,
  required,
  className,
  ...inputProps
}: FormFieldProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId

  const hintId = hint ? `${inputId}-hint` : undefined
  const errorId = error ? `${inputId}-error` : undefined

  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className="form-field">
      <label htmlFor={inputId} className="form-field__label">
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>

      <input
        {...inputProps}
        id={inputId}
        required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={`form-field__input ${className ?? ''}`}
      />

      {hint && (
        <p id={hintId} className="form-field__hint">
          {hint}
        </p>
      )}

      {error && (
        <p id={errorId} className="form-field__error">
          {error}
        </p>
      )}
    </div>
  )
}
