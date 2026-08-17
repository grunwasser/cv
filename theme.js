const themeSelect = document.querySelector('[data-theme-select]');
const themeToggle = document.querySelector('[data-theme-toggle]');
const themeMode = document.querySelector('[data-theme-mode]');
const themePanel = document.querySelector('#theme-panel');
const availableColors = new Set([...themeSelect.options].map((option) => option.value));
const browserColorScheme = matchMedia('(prefers-color-scheme: dark)');

function readPreference(name) {
  try {
    return localStorage.getItem(name);
  } catch {
    return null;
  }
}

function savePreference(name, value) {
  try {
    localStorage.setItem(name, value);
  } catch {
    // Le thème reste utilisable même si le stockage est bloqué par le navigateur.
  }
}

let currentTheme = document.documentElement.dataset.theme;
let darkMode = currentTheme.startsWith('dark_');
let currentColor = darkMode ? currentTheme.slice(5) : currentTheme;
if (!availableColors.has(currentColor)) currentColor = 'blue';

function updateControls() {
  themeSelect.value = currentColor;
  themeMode.setAttribute('aria-checked', String(darkMode));
}

function applyTheme() {
  document.documentElement.dataset.theme = darkMode ? `dark_${currentColor}` : currentColor;
  updateControls();
}

function closeThemePanel() {
  themePanel.hidden = true;
  themeToggle.setAttribute('aria-expanded', 'false');
}

updateControls();

themeToggle.addEventListener('click', () => {
  const willOpen = themePanel.hidden;
  themePanel.hidden = !willOpen;
  themeToggle.setAttribute('aria-expanded', String(willOpen));
  if (willOpen) themeSelect.focus();
});

themeSelect.addEventListener('change', () => {
  currentColor = themeSelect.value;
  savePreference('cv-color', currentColor);
  applyTheme();
});

themeMode.addEventListener('click', () => {
  darkMode = !darkMode;
  savePreference('cv-mode', darkMode ? 'dark' : 'light');
  applyTheme();
});

function followBrowserColorScheme(event) {
  if (readPreference('cv-mode')) return;
  darkMode = event.matches;
  applyTheme();
}

if (typeof browserColorScheme.addEventListener === 'function') {
  browserColorScheme.addEventListener('change', followBrowserColorScheme);
} else if (typeof browserColorScheme.addListener === 'function') {
  browserColorScheme.addListener(followBrowserColorScheme);
}

document.addEventListener('click', (event) => {
  if (!event.target.closest('.theme-settings')) closeThemePanel();
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape' || themePanel.hidden) return;
  closeThemePanel();
  themeToggle.focus();
});
