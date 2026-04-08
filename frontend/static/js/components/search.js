// ── Symbol search with keyboard navigation ──

import { store } from '../store.js';
import { escapeHtml } from '../utils.js';

const POPULAR_SYMBOLS = [
  'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'JPM', 'V', 'WMT',
  'BHP.AX', 'CBA.AX', 'CSL.AX', 'WES.AX', 'NAB.AX', 'ANZ.AX', 'FMG.AX', 'RIO.AX',
  'NFLX', 'AMD', 'INTC', 'DIS', 'PYPL', 'BA', 'GS', 'UBER', 'SQ', 'COIN',
];

export function initSearch() {
  const container = document.getElementById('search-container');

  container.innerHTML = `
    <div class="search-wrapper">
      <div class="search-box" id="search-box">
        <span class="search-icon">⌕</span>
        <input id="search-input" placeholder="Search symbol... (Ctrl+K)" autocomplete="off" />
        <kbd>/</kbd>
      </div>
      <div class="search-dropdown" id="search-dropdown"></div>
    </div>
  `;

  const box = container.querySelector('#search-box');
  const input = container.querySelector('#search-input');
  const dropdown = container.querySelector('#search-dropdown');
  let selectedIdx = 0;
  let filtered = [];
  let isOpen = false;

  function filter() {
    const q = input.value.trim().toLowerCase();
    filtered = q
      ? POPULAR_SYMBOLS.filter(s => s.toLowerCase().includes(q)).slice(0, 10)
      : POPULAR_SYMBOLS.slice(0, 10);
    selectedIdx = 0;
    renderDropdown();
  }

  function renderDropdown() {
    if (!isOpen || filtered.length === 0) {
      dropdown.classList.remove('open');
      return;
    }
    dropdown.classList.add('open');
    dropdown.innerHTML = filtered
      .map(
        (sym, i) =>
          `<div class="search-dropdown-item${i === selectedIdx ? ' selected' : ''}" data-sym="${escapeHtml(sym)}">
            <span class="sym">${escapeHtml(sym)}</span>
          </div>`
      )
      .join('');
  }

  function selectSymbol(sym) {
    store.setActiveSymbol(sym);
    store.addToWatchlist(sym);
    input.value = '';
    isOpen = false;
    dropdown.classList.remove('open');
    box.classList.remove('active');
    input.blur();
  }

  input.addEventListener('input', () => {
    isOpen = true;
    filter();
  });

  input.addEventListener('focus', () => {
    isOpen = true;
    box.classList.add('active');
    filter();
  });

  input.addEventListener('blur', () => {
    setTimeout(() => {
      isOpen = false;
      dropdown.classList.remove('open');
      box.classList.remove('active');
    }, 150);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIdx = Math.min(selectedIdx + 1, filtered.length - 1);
      renderDropdown();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIdx = Math.max(selectedIdx - 1, 0);
      renderDropdown();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (input.value.trim() && filtered.length === 0) {
        selectSymbol(input.value.trim().toUpperCase());
      } else if (filtered[selectedIdx]) {
        selectSymbol(filtered[selectedIdx]);
      }
    } else if (e.key === 'Escape') {
      isOpen = false;
      dropdown.classList.remove('open');
      input.blur();
    }
  });

  // Dropdown click (mousedown fires before blur)
  dropdown.addEventListener('mousedown', (e) => {
    const item = e.target.closest('.search-dropdown-item');
    if (item) selectSymbol(item.dataset.sym);
  });

  // Global shortcut: Ctrl+K or /
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && !(e.target instanceof HTMLInputElement))) {
      e.preventDefault();
      input.focus();
      isOpen = true;
      filter();
    }
  });
}
