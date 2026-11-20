(() => {
  const collectorPage = document.documentElement.hasAttribute('data-collector');
  const key = collectorPage ? 'heimdal.collector.appearance' : 'heimdal.appearance';
  const cookieName = 'heimdal_appearance';
  const localHost = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  const valid = value => value === 'dark' || value === 'light' ? value : null;

  // Local dashboard and collector use different ports. A host-only cookie shares
  // this display setting between them, including direct visits to the collector.
  function sharedPreference() {
    if (!localHost) return null;
    try {
      const entry = document.cookie.split('; ').find(item => item.startsWith(cookieName + '='));
      const value = entry?.slice(cookieName.length + 1);
      return value === 'system' ? value : valid(value);
    } catch {
      return null;
    }
  }

  function remember(value) {
    preference = value;
    if (localHost) {
      try {
        document.cookie = cookieName + '=' + (value ?? 'system') + '; Path=/; SameSite=Lax; Max-Age=31536000';
      } catch { /* The link can still carry the selected appearance. */ }
    }
    try {
      if (value) localStorage.setItem(key, value);
      else localStorage.removeItem(key);
    } catch { /* Keep the selection in memory for this visit. */ }
  }

  const shared = sharedPreference();
  let preference = valid(shared);
  if (!shared) {
    try {
      const saved = valid(localStorage.getItem(key));
      if (saved) remember(saved);
    } catch { /* Use the system setting when storage is blocked. */ }
  }

  // Carry only the appearance across hostnames. Consume the fragment once so
  // refreshing an old link cannot override a newer choice.
  const incoming = collectorPage && /^#theme=(dark|light|system)$/.exec(location.hash);
  if (incoming) {
    remember(valid(incoming[1]));
    history.replaceState(history.state, '', location.pathname + location.search);
  }

  function apply() {
    const theme = preference ?? (system.matches ? 'dark' : 'light');
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.themePreference = preference ?? 'system';
    for (const input of document.querySelectorAll('input[data-theme-switch]')) {
      input.checked = theme === 'dark';
    }
    window.dispatchEvent(new Event('heimdal-appearance'));
  }

  function refreshShared() {
    const shared = sharedPreference();
    if (shared && valid(shared) !== preference) {
      preference = valid(shared);
      apply();
    }
  }

  apply();
  document.addEventListener('DOMContentLoaded', apply, { once: true });
  system.addEventListener('change', apply);
  window.addEventListener('pageshow', refreshShared);
  window.addEventListener('focus', refreshShared);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refreshShared();
  });
  if (localHost) window.cookieStore?.addEventListener('change', refreshShared);
  window.addEventListener('storage', event => {
    if (event.key !== key && event.key !== null) return;
    preference = valid(sharedPreference() ?? event.newValue);
    apply();
  });
  document.addEventListener('change', event => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.hasAttribute('data-theme-switch')) return;
    remember(input.checked ? 'dark' : 'light');
    apply();
  });
})();
