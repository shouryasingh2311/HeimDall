import { useEffect, useRef, type ReactNode } from 'react';

interface DialogProps {
  titleId: string;
  large?: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function Dialog({ titleId, large, onClose, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = ref.current!;
    element.showModal();
    return () => element.close();
  }, []);

  return (
    <dialog ref={ref} aria-labelledby={titleId} className={large ? 'modal-content modal-large' : 'modal-content'}
      onCancel={(event) => { event.preventDefault(); onClose(); }}>
      {children}
    </dialog>
  );
}
