import type { ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

const variants = cva('button', {
  variants: {
    variant: { default: 'button-primary', secondary: 'button-secondary', ghost: 'button-ghost' },
    size: { default: '', small: 'button-small' },
  },
  defaultVariants: { variant: 'default', size: 'default' },
});

// Small local shadcn-style primitive: semantic HTML, variants and composable classes.
export function Button({ className, variant, size, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof variants>) {
  return <button className={twMerge(clsx(variants({ variant, size }), className))} {...props} />;
}
