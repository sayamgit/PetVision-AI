/* Apply before styles render to avoid a flash of the wrong theme. */
(() => {
  const key = 'petvision-theme';
  const preference = window.matchMedia('(prefers-color-scheme: dark)');
  let saved;
  try { saved = localStorage.getItem(key); } catch (_) {}
  let chosen = saved === 'dark' || saved === 'light' ? saved : null;
  const apply = value => {
    document.documentElement.dataset.theme = value;
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      const dark = value === 'dark';
      button.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
      button.setAttribute('aria-pressed', String(dark));
      button.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
      button.querySelector('[data-theme-label]').textContent = dark ? 'Light' : 'Dark';
    });
  };
  apply(chosen || (preference.matches ? 'dark' : 'light'));
  document.addEventListener('DOMContentLoaded', () => {
    apply(document.documentElement.dataset.theme);
    document.querySelectorAll('[data-theme-toggle]').forEach(button => button.addEventListener('click', () => {
      chosen = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      apply(chosen);
      try { localStorage.setItem(key, chosen); } catch (_) {}
    }));
  });
  preference.addEventListener('change', event => { if (!chosen) apply(event.matches ? 'dark' : 'light'); });
})();
