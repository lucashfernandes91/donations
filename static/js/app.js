document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-toast]').forEach((toast) => {
    const close = () => toast.remove();
    toast.querySelector('[data-toast-close]')?.addEventListener('click', close);
    const delay = Number(toast.dataset.toastAutohide);
    if (Number.isFinite(delay) && delay > 0) window.setTimeout(close, delay);
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const dialogs = document.querySelectorAll('[data-delete-dialog]');
  if (!dialogs.length) return;

  const syncPageScroll = () => {
    document.body.classList.toggle('has-open-modal', Boolean(document.querySelector('[data-delete-dialog][open]')));
  };

  document.querySelectorAll('[data-delete-dialog-open]').forEach((trigger) => {
    trigger.addEventListener('click', () => {
      const dialog = document.getElementById(trigger.dataset.deleteDialogOpen);
      if (!dialog || typeof dialog.showModal !== 'function') return;
      dialog.returnFocusTo = trigger;
      if (!dialog.open) dialog.showModal();
      dialog.querySelector('[data-delete-dialog-close]')?.focus();
      syncPageScroll();
    });
  });

  dialogs.forEach((dialog) => {
    dialog.querySelector('[data-delete-dialog-close]')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener('close', () => {
      syncPageScroll();
      dialog.returnFocusTo?.focus();
    });
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const formatDocument = (value) => {
    const digits = value.replace(/\D/g, '').slice(0, 14);
    if (digits.length <= 11) {
      return digits
        .replace(/^(\d{3})(\d)/, '$1.$2')
        .replace(/^(\d{3}\.\d{3})(\d)/, '$1.$2')
        .replace(/^(\d{3}\.\d{3}\.\d{3})(\d)/, '$1-$2');
    }
    return digits
      .replace(/^(\d{2})(\d)/, '$1.$2')
      .replace(/^(\d{2}\.\d{3})(\d)/, '$1.$2')
      .replace(/^(\d{2}\.\d{3}\.\d{3})(\d)/, '$1/$2')
      .replace(/^(\d{2}\.\d{3}\.\d{3}\/\d{4})(\d)/, '$1-$2');
  };

  document.querySelectorAll('[data-document-input]').forEach((input) => {
    const formatInput = () => { input.value = formatDocument(input.value); };
    formatInput();
    input.addEventListener('input', formatInput);
  });
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-donor-filter-picker]').forEach((picker) => {
    const input = picker.querySelector('[data-donor-filter-input]');
    const suggestions = picker.querySelector('[data-donor-filter-suggestions]');
    const status = picker.querySelector('[data-donor-filter-status]');
    if (!input || !suggestions) return;

    let searchTimer;
    let latestRequest = 0;

    const hideSuggestions = () => {
      suggestions.hidden = true;
      input.setAttribute('aria-expanded', 'false');
    };

    const renderResults = (results) => {
      suggestions.replaceChildren();
      results.forEach((donor) => {
        const option = document.createElement('button');
        const name = document.createElement('span');
        option.type = 'button';
        option.className = 'donor-option';
        option.setAttribute('role', 'option');
        name.textContent = donor.name;
        option.append(name);
        option.addEventListener('click', () => {
          input.value = donor.name;
          hideSuggestions();
          input.focus();
        });
        suggestions.append(option);
      });
      suggestions.hidden = results.length === 0;
      input.setAttribute('aria-expanded', String(results.length > 0));
    };

    const searchDonors = async () => {
      const term = input.value.trim();
      if (!term) {
        suggestions.replaceChildren();
        hideSuggestions();
        if (status) status.textContent = '';
        return;
      }
      const requestId = ++latestRequest;
      if (status) status.textContent = 'Buscando doadores cadastrados...';
      const url = new URL(picker.dataset.searchUrl, window.location.origin);
      url.searchParams.set('q', term);
      try {
        const response = await fetch(url, { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('Não foi possível pesquisar doadores.');
        const payload = await response.json();
        if (requestId !== latestRequest) return;
        renderResults(payload.results);
        if (status) status.textContent = payload.results.length
          ? `${payload.results.length} doador(es) encontrado(s).`
          : 'Nenhum doador encontrado.';
      } catch (error) {
        if (requestId !== latestRequest) return;
        suggestions.replaceChildren();
        hideSuggestions();
        if (status) status.textContent = 'Não foi possível pesquisar agora.';
      }
    };

    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    input.addEventListener('input', () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(searchDonors, 150);
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') hideSuggestions();
    });
    document.addEventListener('click', (event) => {
      if (!picker.contains(event.target)) hideSuggestions();
    });
  });
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-collapsible-toggle]').forEach((toggle) => {
    const panel = document.getElementById(toggle.getAttribute('aria-controls'));
    if (!panel) return;

    const setExpanded = (isExpanded) => {
      toggle.setAttribute('aria-expanded', String(isExpanded));
      toggle.setAttribute(
        'aria-label',
        isExpanded ? toggle.dataset.expandedLabel : toggle.dataset.collapsedLabel,
      );
      panel.hidden = !isExpanded;
    };

    toggle.addEventListener('click', () => {
      setExpanded(toggle.getAttribute('aria-expanded') !== 'true');
    });
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const shell = document.querySelector('[data-app-shell]');
  const toggle = document.querySelector('[data-sidebar-toggle]');
  const closeButton = document.querySelector('[data-sidebar-close]');
  const overlay = document.querySelector('[data-sidebar-overlay]');
  if (!shell || !toggle) return;
  const setOpen = (isOpen) => { shell.classList.toggle('is-sidebar-open', isOpen); toggle.setAttribute('aria-expanded', String(isOpen)); };
  toggle.addEventListener('click', () => setOpen(!shell.classList.contains('is-sidebar-open')));
  closeButton?.addEventListener('click', () => setOpen(false));
  overlay?.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') setOpen(false); });
});

document.addEventListener('DOMContentLoaded', () => {
  const interactiveSelector = 'a,button,input,select,textarea,label,summary,[role="button"]';
  const activateRow = (row, event) => {
    if (event.target !== row && event.target.closest(interactiveSelector)) return;
    const modalId = row.dataset.rowModalOpen;
    if (modalId) {
      const modal = document.getElementById(modalId);
      if (!modal || typeof modal.showModal !== 'function') return;
      event.preventDefault();
      modal.showModal();
      document.body.classList.add('has-open-modal');
      modal.querySelector('input:not([type="hidden"]), button')?.focus();
      return;
    }
    if (row.dataset.rowUrl) {
      event.preventDefault();
      window.location.assign(row.dataset.rowUrl);
    }
  };

  document.querySelectorAll('[data-row-url], [data-row-modal-open]').forEach((row) => {
    row.addEventListener('click', (event) => activateRow(row, event));
    row.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') activateRow(row, event);
    });
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const menus = Array.from(document.querySelectorAll('.receipt-menu'));
  if (!menus.length) return;

  const positionMenu = (menu) => {
    const trigger = menu.querySelector('summary');
    const options = menu.querySelector('.receipt-menu-options');
    if (!trigger || !options || !menu.open) return;
    const gap = 6;
    const edge = 8;
    const triggerRect = trigger.getBoundingClientRect();
    const optionsRect = options.getBoundingClientRect();
    let left = triggerRect.right - optionsRect.width;
    let top = triggerRect.bottom + gap;
    left = Math.min(Math.max(edge, left), window.innerWidth - optionsRect.width - edge);
    if (top + optionsRect.height > window.innerHeight - edge) {
      top = Math.max(edge, triggerRect.top - optionsRect.height - gap);
    }
    options.style.left = `${left}px`;
    options.style.top = `${top}px`;
    menu.classList.add('is-positioned');
  };

  const closeMenu = (menu, restoreFocus = false) => {
    if (!menu.open) return;
    menu.open = false;
    menu.classList.remove('is-positioned');
    if (restoreFocus) menu.querySelector('summary')?.focus();
  };

  menus.forEach((menu) => {
    menu.addEventListener('toggle', () => {
      if (!menu.open) {
        menu.classList.remove('is-positioned');
        return;
      }
      menus.forEach((otherMenu) => {
        if (otherMenu !== menu) closeMenu(otherMenu);
      });
      positionMenu(menu);
    });

    menu.querySelector('[data-receipt-menu-close]')?.addEventListener('click', (event) => {
      event.preventDefault();
      closeMenu(menu, true);
    });

    menu.querySelectorAll('.receipt-menu-option').forEach((option) => {
      option.addEventListener('click', () => closeMenu(menu));
    });
  });

  document.addEventListener('click', (event) => {
    menus.forEach((menu) => {
      if (menu.open && !menu.contains(event.target)) closeMenu(menu);
    });
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    const openMenu = menus.find((menu) => menu.open);
    if (openMenu) closeMenu(openMenu, true);
  });

  let positionFrame;
  const repositionMenus = () => {
    window.cancelAnimationFrame(positionFrame);
    positionFrame = window.requestAnimationFrame(() => {
      menus.forEach((menu) => positionMenu(menu));
    });
  };
  window.addEventListener('resize', repositionMenus);
  document.addEventListener('scroll', repositionMenus, true);
});

document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-donation-form]');
  if (!form) return;

  const formatCurrency = (value) => new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', minimumFractionDigits: 2,
  }).format(value);
  const parseMoney = (input) => {
    const rawValue = input.value.trim();
    const value = rawValue.includes(',')
      ? rawValue.replace(/\./g, '').replace(',', '.')
      : rawValue;
    return Number.parseFloat(value) || 0;
  };
  const amountInputs = form.querySelectorAll('[data-money-input]');
  const total = form.querySelector('[data-donation-total]');
  const updateTotal = () => {
    total.textContent = formatCurrency([...amountInputs].reduce((sum, input) => sum + parseMoney(input), 0));
  };
  amountInputs.forEach((input) => input.addEventListener('input', updateTotal));
  updateTotal();

  form.querySelectorAll('[data-donor-picker]').forEach((picker) => {
    const input = picker.querySelector('[data-donor-input]');
    const hiddenInput = picker.querySelector('[data-donor-id]');
    const suggestions = picker.querySelector('[data-donor-suggestions]');
    const status = picker.querySelector('[data-donor-picker-status]');
    const personLabel = picker.dataset.personLabel || 'doador';
    const allowNew = picker.dataset.allowNew === 'true';
    let searchTimer;
    let latestRequest = 0;
    const emptyStatus = () => (
      allowNew
        ? `Comece a digitar para localizar um cadastro ou incluir um novo ${personLabel}.`
        : `Comece a digitar para localizar um ${personLabel} cadastrado.`
    );
    const hideSuggestions = () => {
      suggestions.hidden = true;
      input.setAttribute('aria-expanded', 'false');
    };
    const selectDonor = (donor) => {
      hiddenInput.value = donor.id;
      input.value = donor.name;
      status.textContent = 'Cadastro selecionado.';
      hideSuggestions();
    };
    const renderResults = (results) => {
      suggestions.replaceChildren();
      results.forEach((donor) => {
        const option = document.createElement('button');
        const name = document.createElement('span');
        option.type = 'button';
        option.className = 'donor-option';
        option.setAttribute('role', 'option');
        option.setAttribute('aria-selected', 'false');
        name.textContent = donor.name;
        option.append(name);
        option.addEventListener('click', () => selectDonor(donor));
        suggestions.append(option);
      });
      suggestions.hidden = results.length === 0;
      input.setAttribute('aria-expanded', String(results.length > 0));
    };
    const searchDonors = async () => {
      const term = input.value.trim();
      hiddenInput.value = '';
      if (!term) {
        suggestions.replaceChildren();
        hideSuggestions();
        status.textContent = emptyStatus();
        return;
      }
      const requestId = ++latestRequest;
      status.textContent = 'Buscando cadastros...';
      const url = new URL(picker.dataset.searchUrl, window.location.origin);
      url.searchParams.set('q', term);
      try {
        const response = await fetch(url, { headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('Não foi possível pesquisar cadastros.');
        const payload = await response.json();
        if (requestId !== latestRequest) return;
        renderResults(payload.results);
        status.textContent = payload.results.length
          ? `${payload.results.length} cadastro(s) encontrado(s).`
          : (allowNew ? 'Nenhum cadastro encontrado. Este nome será incluído ao salvar.' : 'Nenhum cadastro encontrado.');
      } catch (error) {
        if (requestId !== latestRequest) return;
        suggestions.replaceChildren();
        hideSuggestions();
        status.textContent = 'Não foi possível pesquisar agora. Você pode continuar o preenchimento.';
      }
    };
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    input.addEventListener('input', () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(searchDonors, 150);
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') hideSuggestions();
    });
    document.addEventListener('click', (event) => { if (!picker.contains(event.target)) hideSuggestions(); });
    status.textContent = emptyStatus();
  });
});
