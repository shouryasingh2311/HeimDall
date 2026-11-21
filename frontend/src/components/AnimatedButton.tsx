import type { ButtonHTMLAttributes, ReactNode } from 'react';
import './animated-button.css';

export interface AnimatedButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children?: ReactNode;
  className?: string;
  as?: 'button';
}

/**
 * AnimatedButton
 * - Theme-aware border shine and text sweep animation.
 * - Hardware-accelerated hover and active tap feedback.
 * - Preserves native button accessibility, types, and form submissions.
 */
export function AnimatedButton({
  children = 'Connect dashboard',
  className = '',
  ...rest
}: AnimatedButtonProps) {
  return (
    <button
      {...rest}
      className={`animated-btn ${className}`.trim()}
    >
      <span className="animated-btn-text">{children}</span>
      <span className="animated-btn-border" aria-hidden="true" />
    </button>
  );
}

export default AnimatedButton;
