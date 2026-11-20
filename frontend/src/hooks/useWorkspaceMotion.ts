import { useEffect, useLayoutEffect, type RefObject } from 'react';
import gsap from 'gsap';
import Lenis from 'lenis';
import 'lenis/dist/lenis.css';

export function useWorkspaceMotion(workspace: RefObject<HTMLElement | null>, view: string) {
  useEffect(() => {
    const media = gsap.matchMedia();
    media.add('(prefers-reduced-motion: no-preference) and (pointer: fine)', () => {
      const scroll = new Lenis({
        lerp: 0.2,
        syncTouch: false,
        allowNestedScroll: true,
        prevent: (node) => node.tagName === 'DIALOG',
      });
      const tick = (seconds: number) => scroll.raf(seconds * 1000);
      gsap.ticker.add(tick);
      return () => {
        gsap.ticker.remove(tick);
        scroll.destroy();
      };
    });
    return () => media.revert();
  }, []);

  useLayoutEffect(() => {
    const panel = workspace.current?.querySelector('[role="tabpanel"]');
    if (!panel) return;
    const media = gsap.matchMedia();
    media.add('(prefers-reduced-motion: no-preference)', () => {
      gsap.from(panel, { y: 4, opacity: 0.9, duration: 0.18, ease: 'power2.out', clearProps: 'transform,opacity' });
    });
    return () => media.revert();
  }, [workspace, view]);
}
