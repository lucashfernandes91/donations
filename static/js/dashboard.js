document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('[data-mixed-chart]');
  const source = document.getElementById('monthly-chart-data');
  if (!container || !source) return;

  const rawData = JSON.parse(source.textContent);
  const data = rawData.map((item) => ({
    ...item,
    count: Number(item.count),
    total: Number(item.total),
    date: new Date(`${item.month}T12:00:00`),
  }));
  const svgNamespace = 'http://www.w3.org/2000/svg';
  const width = Math.max(680, Math.floor(container.clientWidth || 720));
  const height = 254;
  const compact = width <= 720;
  const plot = {
    left: compact ? 42 : 58,
    right: width - (compact ? 58 : 60),
    top: 32,
    bottom: 210,
  };
  const plotWidth = plot.right - plot.left;
  const plotHeight = plot.bottom - plot.top;
  const money = new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 2,
  });
  const month = new Intl.DateTimeFormat('pt-BR', { month: 'short' });
  const createElement = (name, attributes = {}) => {
    const element = document.createElementNS(svgNamespace, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  };
  const niceMaximum = (value) => {
    if (value <= 1) return 1;
    const magnitude = 10 ** Math.floor(Math.log10(value));
    const normalized = value / magnitude;
    return (normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10) * magnitude;
  };
  const formatRevenueAxis = (value) => {
    if (value >= 1000) {
      return `R$ ${(value / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 1 })} mil`;
    }
    return `R$ ${value.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}`;
  };

  const maxCount = niceMaximum(Math.max(...data.map((item) => item.count)));
  const maxTotal = niceMaximum(Math.max(...data.map((item) => item.total)));
  const svg = createElement('svg', {
    viewBox: `0 0 ${width} ${height}`,
    role: 'img',
    'aria-labelledby': 'mixed-chart-svg-title mixed-chart-svg-description',
  });
  const title = createElement('title', { id: 'mixed-chart-svg-title' });
  title.textContent = 'Valor total e quantidade de doações por mês';
  const description = createElement('desc', { id: 'mixed-chart-svg-description' });
  description.textContent = 'Barras verdes representam o valor total arrecadado. Linha azul representa a quantidade de doações.';
  svg.append(title, description);

  for (let tick = 0; tick <= 4; tick += 1) {
    const ratio = tick / 4;
    const y = plot.bottom - ratio * plotHeight;
    svg.append(createElement('line', {
      x1: plot.left, y1: y, x2: plot.right, y2: y, class: 'mixed-chart-grid',
    }));
    const countLabel = createElement('text', {
      x: plot.left - 10, y: y + 4, 'text-anchor': 'end', class: 'mixed-chart-axis-label',
    });
    countLabel.textContent = formatRevenueAxis(maxTotal * ratio);
    const totalLabel = createElement('text', {
      x: plot.right + 10, y: y + 4, 'text-anchor': 'start', class: 'mixed-chart-axis-label',
    });
    totalLabel.textContent = Math.round(maxCount * ratio).toLocaleString('pt-BR');
    svg.append(countLabel, totalLabel);
  }

  const sectionWidth = plotWidth / data.length;
  const barWidth = Math.min(46, sectionWidth * 0.58);
  const points = [];
  const barLabels = [];
  data.forEach((item, index) => {
    const centerX = plot.left + sectionWidth * (index + 0.5);
    const barHeight = (item.total / maxTotal) * plotHeight;
    const bar = createElement('rect', {
      x: centerX - barWidth / 2,
      y: plot.bottom - barHeight,
      width: barWidth,
      height: barHeight,
      rx: 5,
      class: 'mixed-chart-bar',
    });
    const barTitle = createElement('title');
    barTitle.textContent = `${month.format(item.date)}: ${money.format(item.total)}`;
    bar.append(barTitle);
    svg.append(bar);

    const barLabelY = plot.bottom + 20;
    const barLabel = createElement('text', {
      x: centerX, y: barLabelY, 'text-anchor': 'middle', class: 'mixed-chart-bar-label',
    });
    barLabel.textContent = money.format(item.total);
    barLabels.push(barLabel);

    const lineY = plot.bottom - (item.count / maxCount) * plotHeight;
    points.push([centerX, lineY, item, barLabelY]);
    const monthLabel = createElement('text', {
      x: centerX, y: plot.bottom + 33, 'text-anchor': 'middle', class: 'mixed-chart-month-label',
    });
    monthLabel.textContent = month.format(item.date).replace('.', '');
    svg.append(monthLabel);
  });

  const linePath = points.map(([x, y], index) => `${index ? 'L' : 'M'} ${x} ${y}`).join(' ');
  const lineOutline = createElement('path', {
    d: linePath,
    class: 'mixed-chart-line-outline',
  });
  const line = createElement('path', {
    d: linePath,
    class: 'mixed-chart-line',
  });
  svg.append(lineOutline, line);
  barLabels.forEach((label) => svg.append(label));
  points.forEach(([x, y, item, barLabelY]) => {
    const point = createElement('circle', { cx: x, cy: y, r: 3.5, class: 'mixed-chart-point' });
    const pointTitle = createElement('title');
    pointTitle.textContent = `${month.format(item.date)}: ${item.count} doação(ões)`;
    point.append(pointTitle);
    svg.append(point);

    const labelAbove = Math.max(plot.top + 11, y - 10);
    const labelBelow = y + 20;
    const pointLabelY = Math.abs(labelAbove - barLabelY) < 14 && labelBelow <= plot.bottom - 8
      ? labelBelow
      : labelAbove;
    const pointLabel = createElement('text', {
      x, y: pointLabelY, 'text-anchor': 'middle', class: 'mixed-chart-point-label',
    });
    pointLabel.textContent = item.count.toLocaleString('pt-BR');
    svg.append(pointLabel);
  });

  container.replaceChildren(svg);
});

document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('[data-monthly-chart-toggle]');
  const panel = document.querySelector('[data-monthly-chart-panel]');
  if (!toggle || !panel) return;

  toggle.addEventListener('click', () => {
    const shouldCollapse = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!shouldCollapse));
    toggle.setAttribute(
      'aria-label',
      shouldCollapse ? 'Expandir arrecadação e quantidade mensal' : 'Minimizar arrecadação e quantidade mensal',
    );
    panel.hidden = shouldCollapse;
  });
});

document.addEventListener('DOMContentLoaded', () => {
  const triggers = document.querySelectorAll('[data-donation-modal-open]');
  const dialogs = document.querySelectorAll('.donation-modal');
  if (!triggers.length || !dialogs.length) return;

  const syncPageScroll = () => {
    document.body.classList.toggle(
      'has-open-modal',
      Boolean(document.querySelector('.donation-modal[open]')),
    );
  };

  const openDonationModal = (trigger, event) => {
    const action = event.target.closest('[data-donation-row-action]');
    if (action && action !== trigger) return;
    const dialog = document.getElementById(trigger.dataset.donationModalOpen);
    if (!dialog || typeof dialog.showModal !== 'function') return;
    event.preventDefault();
    dialog.returnFocusTo = event.target.closest('a,button,[tabindex]') || trigger;
    if (!dialog.open) dialog.showModal();
    dialog.querySelector('[data-donation-modal-close]')?.focus();
    syncPageScroll();
  };

  triggers.forEach((trigger) => {
    trigger.addEventListener('click', (event) => openDonationModal(trigger, event));
    trigger.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') openDonationModal(trigger, event);
    });
  });

  dialogs.forEach((dialog) => {
    dialog.querySelector('[data-donation-modal-close]')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener('close', () => {
      syncPageScroll();
      dialog.returnFocusTo?.focus();
    });
  });
});
