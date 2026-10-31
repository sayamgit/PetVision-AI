/* Native cross-document transitions: no intercepted links, requests or timers. */
(() => {
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  window.addEventListener('pagereveal', event => {
    if (!event.viewTransition) return;
    // A skipped/interrupted transition rejects ready by design. Consume it so
    // reduced motion, form resubmission and rapid navigation do not log errors.
    event.viewTransition.ready.catch(() => {});
    // Keep urgent care and same-page follow-ups immediate.
    const from = window.navigation?.activation?.from?.url;
    const samePage = from && new URL(from).pathname === location.pathname;
    if (motion.matches || samePage || document.querySelector('.care-alert.emergency,.care-outcome.urgent')) {
      event.viewTransition.skipTransition();
    }
  });
})();
