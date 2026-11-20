import { useSyncExternalStore, type ReactNode } from 'react';

function subscribe(onChange: () => void) {
  window.addEventListener('heimdal-appearance', onChange);
  return () => window.removeEventListener('heimdal-appearance', onChange);
}

function appearance() {
  return document.documentElement.dataset.themePreference ?? 'system';
}

export function CollectorLink({ page, className, children }: {
  page: 'audit' | 'scenarios';
  className?: string;
  children: ReactNode;
}) {
  const theme = useSyncExternalStore(subscribe, appearance);
  return (
    <a href={`http://localhost:9001/${page}#theme=${theme}`} target="_blank" rel="noreferrer" className={className}>
      {children}
    </a>
  );
}
