const contactDialog = document.querySelector('#contact-dialog');
const contactOpeners = document.querySelectorAll('[data-open-contact]');
const contactCloser = document.querySelector('[data-close-contact]');
const earlierExperience = document.querySelector('.earlier');

for (const opener of contactOpeners) {
  opener.addEventListener('click', () => {
    if (typeof contactDialog.showModal === 'function') contactDialog.showModal();
    else contactDialog.setAttribute('open', '');
  });
}

contactCloser.addEventListener('click', () => {
  if (typeof contactDialog.close === 'function') contactDialog.close();
  else contactDialog.removeAttribute('open');
});

contactDialog.addEventListener('click', (event) => {
  if (event.target !== contactDialog) return;
  if (typeof contactDialog.close === 'function') contactDialog.close();
  else contactDialog.removeAttribute('open');
});

requestAnimationFrame(() => {
  const root = document.documentElement;
  // Tolère uniquement la largeur réservée par une éventuelle barre de défilement native.
  const viewportOverflow = root.scrollWidth - root.clientWidth;
  root.dataset.viewportFits = String(viewportOverflow <= 16);
  root.dataset.viewportOverflow = String(viewportOverflow);
});

window.addEventListener('beforeprint', () => {
  earlierExperience.dataset.wasOpen = String(earlierExperience.open);
  earlierExperience.open = true;
});

window.addEventListener('afterprint', () => {
  earlierExperience.open = earlierExperience.dataset.wasOpen === 'true';
  delete earlierExperience.dataset.wasOpen;
});
