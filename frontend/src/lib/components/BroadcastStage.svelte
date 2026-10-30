<script>
  import { createEventDispatcher } from 'svelte';

  export let deck = null;
  export let currentIndex = 0;
  export let drawerOpen = false;
  export let chartsOpen = false;
  export let webcamOpen = false;
  export let tickerOpen = false;
  export let nuanceOpen = false;
  export let cleanObs = false;
  export let embedded = false;
  export let showPautaBtn = false;

  const dispatch = createEventDispatcher();

  $: slides = deck?.slides?.length ? deck.slides : [];
  $: safeIdx = Math.min(Math.max(0, currentIndex), Math.max(0, slides.length - 1));
  $: slide = slides[safeIdx] || {
    shortDate: '01. Vazio',
    timestamp: '',
    title: 'Nenhum slide disponível',
    summary: '',
    summary2: '',
    deep: '',
    code: '',
    nuance_notes: '',
    metricLabel: 'INDICADOR',
    metricVal: '—',
    metricColor: 'var(--amber)',
    metricSub: '',
    specs: [],
    links: []
  };
  $: progressPct = slides.length > 1 ? (safeIdx / (slides.length - 1)) * 91 : 0;
  $: countStr = `${String(safeIdx + 1).padStart(2, '0')} / ${String(slides.length || 1).padStart(2, '0')}`;
  $: tickerText = (deck?.ticker_items || []).join('   ///   ');
  $: safeLinks = (slide.links || []).filter((l) => /^https?:\/\/.+/i.test(String(l?.url || '').trim()));

  function selectSlide(idx) {
    if (idx < 0 || idx >= slides.length) return;
    currentIndex = idx;
    dispatch('change', { currentIndex });
  }

  function toggle(field) {
    if (field === 'drawer') drawerOpen = !drawerOpen;
    if (field === 'charts') chartsOpen = !chartsOpen;
    if (field === 'webcam') webcamOpen = !webcamOpen;
    if (field === 'ticker') tickerOpen = !tickerOpen;
    if (field === 'nuance') nuanceOpen = !nuanceOpen;
    if (field === 'clean') cleanObs = !cleanObs;
    dispatch('state', { currentIndex: safeIdx, drawerOpen, chartsOpen, webcamOpen, tickerOpen, nuanceOpen, cleanObs });
  }

  function barClass(color) {
    if (color === 'crimson' || color === 'btc') return 'chain-btc';
    if (color === 'amber' || color === 'eth') return 'chain-eth';
    if (color === 'cyan' || color === 'trx') return 'chain-trx';
    if (color === 'dim') return 'dim';
    return '';
  }
</script>

<div class="broadcast-root" class:embedded>
  <!-- 1. TOP BAR -->
  <header class="top-bar">
    <div class="top-kpis">
      {#each deck?.kpis || [] as kpi}
        <div class="kpi-pill">
          <span>{kpi.label}</span>
          <strong style="color: {kpi.color || 'var(--amber)'};">{kpi.value}</strong>
        </div>
      {/each}
    </div>

    {#if !cleanObs}
      <div class="top-actions">
        {#if showPautaBtn}
          <button type="button" class="action-btn" on:click={() => dispatch('openPauta')}>
            [ P ] Pauta / RSS
          </button>
        {/if}
        <button type="button" class="action-btn" class:active={nuanceOpen} on:click={() => toggle('nuance')}>
          [ N ] Nuances
        </button>
        <button type="button" class="action-btn" class:active={tickerOpen} on:click={() => toggle('ticker')}>
          [ T ] Ticker
        </button>
        <button type="button" class="action-btn" class:active={chartsOpen} on:click={() => toggle('charts')}>
          [ G ] 3 Gráficos
        </button>
        <button type="button" class="action-btn" class:active={webcamOpen} on:click={() => toggle('webcam')}>
          [ C ] Webcam
        </button>
        {#if !embedded}
          <button type="button" class="action-btn" on:click={() => toggle('clean')} title="Ocultar botões para captura limpa no OBS (Tecla O)">
            [ O ] Limpo OBS
          </button>
        {/if}
      </div>
    {/if}
  </header>

  <!-- 2. TRILHO DE LINHA DO TEMPO INTERATIVA -->
  <nav class="timeline-nav" aria-label="Linha do tempo da apresentação">
    <div class="track-line"></div>
    <div class="track-progress" style="width: {progressPct}%;"></div>
    <div class="nodes-wrapper">
      {#each slides as item, idx}
        <button
          type="button"
          class="nav-node"
          class:active={idx === safeIdx}
          class:past={idx < safeIdx}
          on:click={() => selectSlide(idx)}
        >
          <div class="node-dot"></div>
          <span class="node-date">{item.shortDate}</span>
        </button>
      {/each}
    </div>
  </nav>

  <!-- 3. PALCO PRINCIPAL DO SLIDE -->
  <main class="stage">
    <section class="slide-main">
      <div>
        <div class="slide-header-meta">
          <span class="slide-counter">{countStr}</span>
          <span class="slide-timestamp">{slide.timestamp || ''}</span>
        </div>

        <h1 class="slide-headline">{slide.title}</h1>

        {#if slide.summary}
          <p class="slide-summary">{slide.summary}</p>
        {/if}
        {#if slide.summary2}
          <p class="slide-summary-2">{slide.summary2}</p>
        {/if}

        {#if nuanceOpen && !cleanObs}
          <div class="nuance-card">
            <div class="nuance-label">ROTEIRO DE ENSAIO // NOTAS DE NUANCE (OCULTO NO MODO LIMPO OBS)</div>
            <p>{slide.nuance_notes || 'Sem notas de nuance cadastradas neste capítulo.'}</p>
          </div>
        {/if}
      </div>

      {#if slide.deep || slide.code}
        <div class="expand-section">
          <button type="button" class="expand-trigger" on:click={() => toggle('drawer')}>
            <span>{drawerOpen ? '[ - ]' : '[ + ]'}</span>
            Expandir Contexto, Evidências &amp; Nuances (Tecla Espaço)
          </button>
          <div class="expand-drawer" class:open={drawerOpen}>
            <div class="drawer-inner">
              {#if slide.deep}
                <p class="drawer-text">{slide.deep}</p>
              {/if}
              {#if slide.code}
                <div class="drawer-code">{slide.code}</div>
              {/if}
            </div>
          </div>
        </div>
      {/if}
    </section>

    <aside class="slide-sidebar">
      <div>
        <div class="sidebar-metric-box">
          <span class="sidebar-metric-label">{slide.metricLabel || 'INDICADOR CHAVE'}</span>
          <div class="sidebar-metric-val" style="color: {slide.metricColor || '#fff'};">
            {slide.metricVal || '—'}
          </div>
          {#if slide.metricSub}
            <div class="sidebar-metric-sub">{slide.metricSub}</div>
          {/if}
        </div>

        {#if slide.specs?.length}
          <ul class="sidebar-details-list">
            {#each slide.specs as spec}
              <li>
                <span>{spec[0] || ''}</span>
                <span>{spec[1] || ''}</span>
              </li>
            {/each}
          </ul>
        {/if}

        {#if safeLinks.length}
          <div class="sidebar-sources">
            {#each safeLinks as link}
              <a href={link.url} target="_blank" rel="noopener noreferrer" class="src-btn">
                <span>{link.label || link.url}</span>
                <span>↗</span>
              </a>
            {/each}
          </div>
        {/if}
      </div>

      <div class="webcam-frame" class:visible={webcamOpen}>
        [ ÁREA RESERVADA PARA CÂMERA / OBS (16:9) ]
      </div>
    </aside>

    <!-- 4. OVERLAY DE COMPOSIÇÕES GRÁFICAS (TECLA 'G') -->
    {#if chartsOpen}
      <section class="charts-modal open">
        {#each (deck?.charts?.length ? deck.charts : []) as card}
          <div class="modal-card">
            <h3>{card.title}</h3>
            {#if card.subtitle}
              <p>{card.subtitle}</p>
            {/if}

            {#each card.rows || [] as row}
              <div class="scale-row">
                <span class="row-lbl">{row.label}</span>
                <div class="scale-bar-wrap">
                  <div class="scale-bar {barClass(row.color)}" style="width: {Math.min(100, Math.max(0, Number(row.pct) || 0))}%;"></div>
                </div>
                <span class="row-val">{row.displayValue}</span>
              </div>
            {/each}

            {#if card.footerTitle || card.footerText}
              <div class="sub-section-title">{card.footerTitle || 'Nota'}</div>
              <p style="margin-bottom: 0;">{card.footerText}</p>
            {/if}
          </div>
        {:else}
          <div class="modal-card" style="grid-column: 1 / -1;">
            <h3>Sem gráficos configurados neste roteiro</h3>
            <p>Adicione barras comparativas na aba "Gráficos [G]" do Modo Estúdio ou gere a partir de um Dossiê.</p>
          </div>
        {/each}
      </section>
    {/if}
  </main>

  <!-- 5. BARRA INFERIOR: TICKER DE LIVE OU CONTROLES -->
  <footer class="bottom-deck">
    {#if tickerOpen && tickerText}
      <div class="ticker-wrap">
        <span class="ticker-badge">● GIRO AO VIVO</span>
        <div class="ticker-marquee">
          <div class="ticker-track">{tickerText}   ///   {tickerText}</div>
        </div>
      </div>
    {:else if !cleanObs}
      <div class="deck-shortcuts">
        <span><kbd class="kbd">←</kbd> <kbd class="kbd">→</kbd> Slides</span>
        <span><kbd class="kbd">Espaço</kbd> Detalhes</span>
        <span><kbd class="kbd">N</kbd> Nuances</span>
        <span><kbd class="kbd">G</kbd> Gráficos</span>
        <span><kbd class="kbd">T</kbd> Ticker</span>
        <span><kbd class="kbd">C</kbd> Câmera</span>
        {#if !embedded}
          <span><kbd class="kbd">O</kbd> Limpo OBS</span>
        {/if}
      </div>
      <div class="deck-nav-btns">
        <button type="button" class="nav-arrow" on:click={() => selectSlide(safeIdx - 1)}>← Anterior</button>
        <button type="button" class="nav-arrow" on:click={() => selectSlide(safeIdx + 1)}>Próximo →</button>
      </div>
    {:else}
      <div class="clean-footer">
        <span style="color: var(--amber); font-weight: 700;">CONTRAPONTO</span>
        <span>{deck?.titulo || ''}</span>
      </div>
    {/if}
  </footer>
</div>

<style>
  .broadcast-root {
    --bg: #050505;
    --surface: #0b0b0d;
    --surface-2: #121216;
    --ink: #e8e8e3;
    --ink-dim: #8a8a84;
    --line: #242422;
    --line-bright: #4a4a46;
    --crimson: #ff2a2a;
    --amber: #ff9900;
    --cyan: #00e5ff;
    --lime: #a6ff00;

    background-color: var(--bg);
    color: var(--ink);
    font-family: 'JetBrains Mono', monospace;
    height: 100vh;
    width: 100vw;
    overflow: hidden;
    display: grid;
    grid-template-rows: 54px 92px 1fr 50px;
    background-image:
      linear-gradient(to right, rgba(255, 255, 255, 0.012) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(255, 255, 255, 0.012) 1px, transparent 1px);
    background-size: 40px 40px;
    user-select: none;
    position: relative;
  }

  .broadcast-root.embedded {
    width: 100%;
    height: 100%;
    min-height: 640px;
    border: 1px solid var(--line-bright);
  }

  .top-bar {
    border-bottom: 1px solid var(--line);
    background: #000;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 22px;
    gap: 12px;
    overflow-x: auto;
  }

  .top-kpis {
    display: flex;
    gap: 20px;
    font-size: 11px;
    white-space: nowrap;
  }

  .kpi-pill {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .kpi-pill span {
    color: var(--ink-dim);
  }

  .kpi-pill strong {
    font-size: 12px;
  }

  .top-actions {
    display: flex;
    gap: 7px;
    flex-shrink: 0;
  }

  .action-btn {
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--line-bright);
    padding: 5px 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .action-btn:hover,
  .action-btn.active {
    background: var(--ink);
    color: #000;
    border-color: #fff;
    font-weight: 700;
  }

  .timeline-nav {
    border-bottom: 1px solid var(--line);
    background: var(--surface);
    padding: 0 24px;
    display: flex;
    align-items: center;
    position: relative;
    overflow-x: auto;
  }

  .track-line {
    position: absolute;
    left: 48px;
    right: 48px;
    top: 42%;
    height: 2px;
    background: var(--line-bright);
    z-index: 1;
  }

  .track-progress {
    position: absolute;
    left: 48px;
    top: 42%;
    height: 2px;
    background: var(--amber);
    z-index: 2;
    transition: width 0.35s cubic-bezier(0.22, 1, 0.36, 1);
  }

  .nodes-wrapper {
    display: flex;
    justify-content: space-between;
    width: 100%;
    position: relative;
    z-index: 3;
    gap: 6px;
  }

  .nav-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: pointer;
    background: transparent;
    border: none;
    flex: 1;
    min-width: 72px;
    padding: 0;
  }

  .node-dot {
    width: 15px;
    height: 15px;
    background: #000;
    border: 2px solid var(--line-bright);
    margin-bottom: 9px;
    transition: all 0.2s;
  }

  .nav-node:hover .node-dot {
    border-color: #fff;
    transform: scale(1.2);
  }

  .nav-node.active .node-dot {
    width: 19px;
    height: 19px;
    background: var(--ink);
    border-color: #fff;
    box-shadow: 0 0 15px rgba(255, 255, 255, 0.45);
  }

  .nav-node.past .node-dot {
    background: var(--amber);
    border-color: var(--amber);
  }

  .node-date {
    font-size: 10px;
    color: var(--ink-dim);
    font-weight: 600;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 115px;
  }

  .nav-node.active .node-date {
    color: #fff;
    font-weight: 700;
  }

  .stage {
    position: relative;
    display: grid;
    grid-template-columns: 1fr 410px;
    height: 100%;
    overflow: hidden;
  }

  .broadcast-root.embedded .stage {
    grid-template-columns: 1fr 330px;
  }

  .slide-main {
    padding: 30px 40px;
    border-right: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow-y: auto;
  }

  .slide-header-meta {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 14px;
  }

  .slide-counter {
    font-size: 11.5px;
    font-weight: 700;
    padding: 3px 10px;
    border: 1px solid var(--line-bright);
    color: var(--ink);
    background: #000;
  }

  .slide-timestamp {
    font-size: 12px;
    color: var(--amber);
    font-weight: 600;
  }

  .slide-headline {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: clamp(2rem, 3.1vw, 3.1rem);
    line-height: 1.06;
    color: #fff;
    font-weight: 400;
    margin-bottom: 16px;
    max-width: 34ch;
  }

  .slide-summary {
    font-size: 14px;
    line-height: 1.62;
    color: #d6d6d0;
    max-width: 78ch;
    margin-bottom: 12px;
  }

  .slide-summary-2 {
    font-size: 13px;
    line-height: 1.58;
    color: #a8a8a2;
    max-width: 78ch;
    margin-bottom: 18px;
  }

  .nuance-card {
    background: #10140a;
    border: 1px solid rgba(166, 255, 0, 0.35);
    border-left: 3px solid var(--lime);
    padding: 12px 16px;
    margin-bottom: 16px;
    max-width: 78ch;
  }

  .nuance-label {
    font-size: 9.5px;
    letter-spacing: 0.08em;
    color: var(--lime);
    font-weight: 700;
    margin-bottom: 5px;
  }

  .nuance-card p {
    font-size: 12.5px;
    line-height: 1.55;
    color: #e4f5c3;
  }

  .expand-section {
    margin-top: auto;
  }

  .expand-trigger {
    background: var(--surface-2);
    color: #fff;
    border: 1px solid var(--line-bright);
    padding: 10px 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 10px;
  }

  .expand-trigger:hover {
    border-color: var(--amber);
    color: var(--amber);
  }

  .expand-drawer {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.35s cubic-bezier(0.22, 1, 0.36, 1), margin-top 0.25s;
    background: #09090b;
    border-left: 3px solid var(--amber);
  }

  .expand-drawer.open {
    max-height: 360px;
    margin-top: 12px;
    border: 1px solid var(--line-bright);
    border-left: 3px solid var(--amber);
    overflow-y: auto;
  }

  .drawer-inner {
    padding: 16px 20px;
  }

  .drawer-text {
    font-size: 12.5px;
    line-height: 1.6;
    color: #c4c4be;
    margin-bottom: 10px;
  }

  .drawer-code {
    background: #000;
    border: 1px solid var(--line);
    padding: 8px 12px;
    font-size: 11px;
    color: var(--cyan);
  }

  .slide-sidebar {
    background: var(--surface);
    padding: 26px 24px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    overflow-y: auto;
  }

  .sidebar-metric-box {
    border: 1px solid var(--line-bright);
    background: #000;
    padding: 18px 20px;
    margin-bottom: 18px;
  }

  .sidebar-metric-label {
    font-size: 10px;
    color: var(--ink-dim);
    margin-bottom: 6px;
    display: block;
    letter-spacing: 0.08em;
  }

  .sidebar-metric-val {
    font-family: 'Instrument Serif', serif;
    font-size: 2.9rem;
    line-height: 1;
    color: #fff;
    margin-bottom: 8px;
  }

  .sidebar-metric-sub {
    font-size: 11px;
    color: var(--ink-dim);
    line-height: 1.4;
  }

  .sidebar-details-list {
    list-style: none;
    border-top: 1px solid var(--line);
    margin-bottom: 18px;
  }

  .sidebar-details-list li {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px dotted var(--line);
    font-size: 11px;
    gap: 10px;
  }

  .sidebar-details-list li span:first-child {
    color: var(--ink-dim);
  }

  .sidebar-details-list li span:last-child {
    color: #fff;
    font-weight: 600;
    text-align: right;
  }

  .sidebar-sources {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .src-btn {
    display: flex;
    justify-content: space-between;
    align-items: center;
    text-decoration: none;
    color: var(--ink);
    background: var(--bg);
    border: 1px solid var(--line-bright);
    padding: 7px 11px;
    font-size: 10.5px;
    transition: all 0.15s;
  }

  .src-btn:hover {
    border-color: #fff;
    color: #fff;
    transform: translateX(2px);
  }

  .webcam-frame {
    display: none;
    height: 175px;
    border: 1px dashed var(--line-bright);
    background: rgba(0, 0, 0, 0.65);
    align-items: center;
    justify-content: center;
    color: var(--ink-dim);
    font-size: 10.5px;
    margin-top: 14px;
    flex-shrink: 0;
    text-align: center;
    padding: 8px;
  }

  .webcam-frame.visible {
    display: flex;
  }

  .charts-modal {
    position: absolute;
    inset: 0;
    background: rgba(5, 5, 5, 0.97);
    backdrop-filter: blur(10px);
    z-index: 40;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    padding: 28px 32px;
    align-items: stretch;
    overflow-y: auto;
  }

  .modal-card {
    background: var(--surface);
    border: 1px solid var(--line-bright);
    padding: 22px;
    display: flex;
    flex-direction: column;
  }

  .modal-card h3 {
    font-family: 'Instrument Serif', serif;
    font-size: 1.75rem;
    font-weight: 400;
    margin-bottom: 6px;
    color: #fff;
  }

  .modal-card p {
    color: var(--ink-dim);
    font-size: 11px;
    margin-bottom: 18px;
    line-height: 1.45;
  }

  .scale-row {
    display: grid;
    grid-template-columns: 120px 1fr 68px;
    align-items: center;
    gap: 8px;
    margin-bottom: 11px;
    font-size: 11px;
  }

  .row-lbl {
    color: #fff;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .row-val {
    text-align: right;
    color: var(--ink);
    font-weight: 600;
  }

  .scale-bar-wrap {
    height: 16px;
    background: #000;
    border: 1px solid var(--line);
  }

  .scale-bar {
    height: 100%;
    background: repeating-linear-gradient(45deg, var(--crimson), var(--crimson) 4px, #800d0d 4px, #800d0d 8px);
  }

  .scale-bar.chain-eth { background: var(--amber); }
  .scale-bar.chain-btc { background: var(--crimson); }
  .scale-bar.chain-trx { background: var(--cyan); }
  .scale-bar.dim { background: var(--line-bright); }

  .sub-section-title {
    font-size: 10.5px;
    color: var(--amber);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 16px 0 8px 0;
    padding-top: 12px;
    border-top: 1px solid var(--line);
  }

  .bottom-deck {
    border-top: 1px solid var(--line);
    background: #000;
    padding: 0 22px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    overflow: hidden;
  }

  .deck-shortcuts {
    display: flex;
    gap: 14px;
    color: var(--ink-dim);
    overflow-x: auto;
    white-space: nowrap;
  }

  .kbd {
    background: var(--surface-2);
    border: 1px solid var(--line-bright);
    color: #fff;
    padding: 2px 6px;
    font-size: 10px;
  }

  .deck-nav-btns {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }

  .nav-arrow {
    background: var(--surface);
    color: #fff;
    border: 1px solid var(--line-bright);
    padding: 6px 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    cursor: pointer;
    font-weight: 600;
  }

  .nav-arrow:hover {
    background: #fff;
    color: #000;
  }

  .clean-footer {
    display: flex;
    justify-content: space-between;
    width: 100%;
    font-size: 11px;
    color: var(--ink-dim);
  }

  .ticker-wrap {
    display: flex;
    align-items: center;
    width: 100%;
    gap: 14px;
    overflow: hidden;
  }

  .ticker-badge {
    background: var(--crimson);
    color: #fff;
    font-weight: 700;
    font-size: 10.5px;
    padding: 4px 10px;
    letter-spacing: 0.06em;
    flex-shrink: 0;
  }

  .ticker-marquee {
    overflow: hidden;
    flex: 1;
    white-space: nowrap;
  }

  .ticker-track {
    display: inline-block;
    padding-left: 20%;
    animation: ticker-scroll 42s linear infinite;
    color: #fff;
    font-size: 12px;
  }

  @keyframes ticker-scroll {
    0% { transform: translateX(0); }
    100% { transform: translateX(-50%); }
  }
</style>
