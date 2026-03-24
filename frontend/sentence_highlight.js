/**
 * AntiplagiatPRO — Sentence Highlight
 * =====================================
 * Backend dan kelgan sentence_highlights ni
 * frontendda rangli ko'rsatish.
 *
 * Ishlatish:
 *   SentenceHighlight.render(container, sentence_highlights, lang)
 *   SentenceHighlight.clear(container)
 */

const SentenceHighlight = (() => {

  // ── RANGLAR ──────────────────────────────────────────────
  const COLORS = {
    exact:   { bg: '#FEE2E2', border: '#EF4444', text: '#991B1B', label: '100%' },
    similar: { bg: '#FEF3C7', border: '#F59E0B', text: '#92400E', label: '~'    },
    low:     { bg: '#FEF9C3', border: '#EAB308', text: '#713F12', label: '~'    },
    clean:   { bg: 'transparent', border: 'transparent', text: 'inherit', label: '' },
  };

  // ── i18n LABEL LARI ───────────────────────────────────────
  const LABELS = {
    uz: {
      title:       'Matn tahlili',
      legend_plag: 'Plagiat jumla',
      legend_sim:  'O\'xshash jumla',
      legend_ok:   'Original',
      source:      'Manba',
      score:       'O\'xshashlik',
      type_exact:  'Aniq nusxa',
      type_similar:'Parafraz/o\'xshash',
      no_highlights:'Plagiat topilmadi',
      sentences:   'ta jumla tekshirildi',
      found:       'ta plagiat topildi',
    },
    ru: {
      title:       'Анализ текста',
      legend_plag: 'Плагиат',
      legend_sim:  'Похожий фрагмент',
      legend_ok:   'Оригинал',
      source:      'Источник',
      score:       'Схожесть',
      type_exact:  'Точная копия',
      type_similar:'Перефраз/похожий',
      no_highlights:'Плагиат не найден',
      sentences:   'предл. проверено',
      found:       'с плагиатом',
    },
    en: {
      title:       'Text analysis',
      legend_plag: 'Plagiarism',
      legend_sim:  'Similar passage',
      legend_ok:   'Original',
      source:      'Source',
      score:       'Match',
      type_exact:  'Exact copy',
      type_similar:'Paraphrase/similar',
      no_highlights:'No plagiarism found',
      sentences:   'sentences checked',
      found:       'with plagiarism',
    },
  };

  function L(lang, key) {
    const dict = LABELS[lang] || LABELS.uz;
    return dict[key] || key;
  }

  // ── TOOLTIP ───────────────────────────────────────────────
  function makeTooltip(h, lang) {
    if (!h.is_plagiarism) return '';
    const typeLabel = h.match_type === 'exact'
      ? L(lang, 'type_exact')
      : L(lang, 'type_similar');
    return `
      <div class="sh-tooltip" role="tooltip">
        <div class="sh-tooltip-row">
          <span class="sh-tooltip-label">${L(lang,'score')}:</span>
          <span class="sh-tooltip-val">${h.match_score}%</span>
        </div>
        <div class="sh-tooltip-row">
          <span class="sh-tooltip-label">${L(lang,'source')}:</span>
          <span class="sh-tooltip-val">${h.match_source || '—'}</span>
        </div>
        <div class="sh-tooltip-row">
          <span class="sh-tooltip-label">Tur:</span>
          <span class="sh-tooltip-val">${typeLabel}</span>
        </div>
        ${h.matched_text ? `
        <div class="sh-tooltip-matched">
          "${h.matched_text.slice(0, 80)}${h.matched_text.length > 80 ? '…' : ''}"
        </div>` : ''}
      </div>
    `;
  }

  // ── HTML RENDER ───────────────────────────────────────────
  function render(container, highlights, lang = 'uz') {
    if (!container || !highlights || !highlights.length) return;
    lang = lang || 'uz';

    const plagCount  = highlights.filter(h => h.is_plagiarism).length;
    const totalCount = highlights.length;

    const css = `
      <style id="sh-style">
        .sh-wrap{font-family:inherit;line-height:1.85;font-size:14px;color:var(--color-text-primary,#0D0F14)}
        .sh-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:8px}
        .sh-title{font-size:14px;font-weight:600;color:var(--color-text-primary,#0D0F14)}
        .sh-stats{font-size:12px;color:var(--color-text-secondary,#7A7F94)}
        .sh-legend{display:flex;gap:14px;margin-bottom:12px;flex-wrap:wrap}
        .sh-legend-item{display:flex;align-items:center;gap:5px;font-size:12px;color:var(--color-text-secondary,#7A7F94)}
        .sh-legend-dot{width:12px;height:12px;border-radius:2px;flex-shrink:0}
        .sh-body{position:relative}
        .sh-sent{position:relative;display:inline;cursor:default}
        .sh-sent.plag{border-radius:3px;padding:1px 2px}
        .sh-sent.exact{background:#FEE2E2;border-bottom:2px solid #EF4444}
        .sh-sent.similar{background:#FEF3C7;border-bottom:2px solid #F59E0B}
        .sh-sent.low{background:#FEF9C3;border-bottom:1px dashed #EAB308}
        .sh-sent:hover .sh-tooltip{display:block}
        .sh-tooltip{
          display:none;position:absolute;z-index:200;
          bottom:calc(100% + 8px);left:0;
          background:var(--color-background-primary,#fff);
          border:1px solid var(--color-border-tertiary,#E4E7F0);
          border-radius:8px;padding:10px 12px;
          min-width:220px;max-width:320px;
          box-shadow:0 4px 20px rgba(0,0,0,.12);
          font-size:12px;line-height:1.5;
          pointer-events:none;white-space:normal;
        }
        .sh-tooltip-row{display:flex;gap:6px;margin-bottom:4px}
        .sh-tooltip-label{color:var(--color-text-secondary,#7A7F94);min-width:70px;flex-shrink:0}
        .sh-tooltip-val{font-weight:500;color:var(--color-text-primary,#0D0F14)}
        .sh-tooltip-matched{
          margin-top:6px;padding-top:6px;
          border-top:1px solid var(--color-border-tertiary,#E4E7F0);
          color:var(--color-text-secondary,#7A7F94);font-style:italic;
        }
        .sh-empty{
          text-align:center;padding:24px;
          color:var(--color-text-secondary,#7A7F94);
          font-size:14px;background:var(--color-background-secondary,#F7F8FC);
          border-radius:8px;
        }
        .sh-sent-space{display:inline}
      </style>
    `;

    // Agar plagiat yo'q
    if (plagCount === 0) {
      container.innerHTML = css + `
        <div class="sh-empty">
          ✅ ${L(lang, 'no_highlights')}
        </div>
      `;
      return;
    }

    // Legend
    const legend = `
      <div class="sh-legend">
        <div class="sh-legend-item">
          <div class="sh-legend-dot" style="background:#FEE2E2;border:1.5px solid #EF4444"></div>
          ${L(lang,'legend_plag')} (aniq)
        </div>
        <div class="sh-legend-item">
          <div class="sh-legend-dot" style="background:#FEF3C7;border:1.5px solid #F59E0B"></div>
          ${L(lang,'legend_sim')}
        </div>
        <div class="sh-legend-item">
          <div class="sh-legend-dot" style="background:var(--color-background-secondary,#F7F8FC);border:1px solid #ccc"></div>
          ${L(lang,'legend_ok')}
        </div>
      </div>
    `;

    // Jumlalarni render qilish
    const sentenceHtml = highlights.map(h => {
      let cls = '';
      if (h.is_plagiarism) {
        if (h.match_type === 'exact')           cls = 'plag exact';
        else if (h.match_score >= 75)           cls = 'plag similar';
        else                                    cls = 'plag low';
      }

      const tooltip = makeTooltip(h, lang);
      const escaped = h.sentence
        .replace(/&/g,'&amp;')
        .replace(/</g,'&lt;')
        .replace(/>/g,'&gt;');

      if (cls) {
        return `<span class="sh-sent ${cls}">${escaped}${tooltip}</span><span class="sh-sent-space"> </span>`;
      }
      return `<span class="sh-sent">${escaped}</span><span class="sh-sent-space"> </span>`;
    }).join('');

    container.innerHTML = css + `
      <div class="sh-wrap">
        <div class="sh-header">
          <div class="sh-title">${L(lang,'title')}</div>
          <div class="sh-stats">
            ${totalCount} ${L(lang,'sentences')} · 
            <strong style="color:#EF4444">${plagCount}</strong> ${L(lang,'found')}
          </div>
        </div>
        ${legend}
        <div class="sh-body">${sentenceHtml}</div>
      </div>
    `;
  }

  function clear(container) {
    if (container) container.innerHTML = '';
  }

  return { render, clear };
})();

window.SentenceHighlight = SentenceHighlight;
