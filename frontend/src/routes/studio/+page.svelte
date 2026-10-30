<script>
  import { onDestroy, onMount } from 'svelte';
  import { page } from '$app/stores';
  import BroadcastStage from '$lib/components/BroadcastStage.svelte';
  import {
    DEMO_FALLBACK_DECK,
    createDeck,
    createDeckFromEvent,
    createDeckFromLiveFeed,
    createLiveSyncClient,
    deleteDeck,
    fetchArticles,
    fetchDeck,
    fetchDecks,
    fetchEvents,
    getDeckExportHtmlUrl,
    suggestSlideNuance,
    updateDeck
  } from '$lib/api.js';

  let decks = [];
  let events = [];
  let articles = [];
  let selectedEventId = '';
  let deck = structuredClone(DEMO_FALLBACK_DECK);
  let currentIndex = 0;
  let activeTab = 'slides';
  let statusMsg = '';
  let liveMirror = true;
  let wsConnected = false;
  let syncChannel = null;
  let angleHint = '';
  let suggestingNuance = false;

  // Estados espelhados no preview e no Modo Live
  let drawerOpen = false;
  let chartsOpen = false;
  let webcamOpen = false;
  let tickerOpen = false;
  let nuanceOpen = true;

  const COLOR_PRESETS = [
    { label: 'Âmbar', value: 'var(--amber)' },
    { label: 'Carmesim', value: 'var(--crimson)' },
    { label: 'Ciano', value: 'var(--cyan)' },
    { label: 'Verde-Lima', value: 'var(--lime)' }
  ];

  function broadcastToLive(forceDeck = false) {
    if (!liveMirror || !syncChannel || !deck) return;
    syncChannel.send({
      type: 'SYNC_STATE',
      forceDeck,
      deck,
      currentIndex,
      drawerOpen,
      chartsOpen,
      webcamOpen,
      tickerOpen
    });
  }

  function selectStudioSlide(idx) {
    currentIndex = idx;
    broadcastToLive(false);
  }

  function flash(msg) {
    statusMsg = msg;
    setTimeout(() => {
      if (statusMsg === msg) statusMsg = '';
    }, 3000);
  }

  async function initStudio() {
    const [dList, evData, artData] = await Promise.all([
      fetchDecks(),
      fetchEvents({ limit: 30 }),
      fetchArticles({ limit: 40 })
    ]);
    decks = dList;
    events = evData.items || [];
    articles = artData.items || [];
    if (events.length) selectedEventId = events[0].id;

    const paramEvent = $page.url.searchParams.get('from_event');
    const paramDeck = $page.url.searchParams.get('deck');

    if (paramEvent) {
      await handleGenerateFromEvent(paramEvent);
    } else if (paramDeck) {
      deck = await fetchDeck(paramDeck);
    } else if (decks.length) {
      deck = await fetchDeck(decks[0].id);
    }
    ensureSlideDefaults();
    broadcastToLive(true);
  }

  function ensureSlideDefaults() {
    if (!deck.slides || deck.slides.length === 0) {
      deck.slides = [emptySlide(1)];
    }
    if (!deck.kpis) deck.kpis = [];
    if (!deck.charts) deck.charts = [];
    if (!deck.ticker_items) deck.ticker_items = [];
    currentIndex = Math.min(currentIndex, deck.slides.length - 1);
  }

  function emptySlide(num) {
    return {
      shortDate: `${String(num).padStart(2, '0')}. Capítulo`,
      timestamp: 'Contexto // Recorte',
      title: 'Título do novo capítulo ou nuance',
      summary: 'Primeiro parágrafo apresentando o núcleo factual deste ponto.',
      summary2: 'Segundo parágrafo expondo a tensão, contradição ou recorte editorial.',
      deep: 'Detalhes técnicos, históricos ou omissões que abrem na tecla Espaço.',
      code: 'Citação literal verificada ou síntese em 1 linha.',
      nuance_notes: 'Notas de fala: tom, pausa dramática, ironia ou transição para o próximo slide.',
      metricLabel: 'INDICADOR CHAVE',
      metricVal: '—',
      metricColor: 'var(--amber)',
      metricSub: 'Explicação curta do número acima.',
      specs: [['Eixo', 'Valor']],
      links: []
    };
  }

  async function handleSelectDeck(e) {
    const id = e.target.value;
    if (!id) return;
    deck = await fetchDeck(id);
    currentIndex = 0;
    ensureSlideDefaults();
    broadcastToLive(true);
  }

  async function handleSave() {
    const payload = {
      titulo: deck.titulo || 'Roteiro sem título',
      modo: deck.modo || 'ensaio',
      event_id: deck.event_id || null,
      kpis: deck.kpis || [],
      slides: deck.slides || [],
      charts: deck.charts || [],
      ticker_items: deck.ticker_items || []
    };
    try {
      const canPut = deck.id && !deck.id.startsWith('local-') && !deck.id.startsWith('demo-');
      if (canPut) {
        try {
          deck = await updateDeck(deck.id, payload);
        } catch (err) {
          if (err.status === 404) {
            deck = await createDeck(payload);
          } else {
            throw err;
          }
        }
      } else {
        deck = await createDeck(payload);
      }
      decks = await fetchDecks();
      broadcastToLive(true);
      flash('✓ Salvo no banco e sincronizado com o Modo Live / OBS.');
    } catch (err) {
      broadcastToLive(true);
      if (err?.status) {
        flash(`⚠ Erro ao salvar (${err.status}): ${err.message}`);
      } else {
        flash('⚠ API offline — edições mantidas na sessão atual.');
      }
    }
  }

  async function handleSuggestNuance() {
    if (!activeSlide || suggestingNuance) return;
    suggestingNuance = true;
    try {
      const res = await suggestSlideNuance({
        deck_title: deck.titulo,
        slide: activeSlide,
        angle_hint: angleHint
      });
      activeSlide.nuance_notes = res.nuance_notes;
      activeSlide.summary2 = res.summary2;
      activeSlide.deep = res.deep;
      deck.slides = [...deck.slides];
      broadcastToLive(false);
      flash('✨ Nuance, contraponto e gaveta refinados pelo LLM local!');
    } catch (err) {
      flash(`⚠ LLM indisponível: ${err.message}`);
    } finally {
      suggestingNuance = false;
    }
  }

  async function handleNewBlankEssay() {
    const payload = {
      titulo: 'Novo Ensaio Crítico (Rascunho)',
      modo: 'ensaio',
      event_id: null,
      kpis: [
        { label: 'Formato:', value: 'ENSAIO', color: 'var(--lime)' },
        { label: 'Status:', value: 'EM ROTEIRO', color: 'var(--amber)' }
      ],
      slides: [emptySlide(1)],
      charts: [],
      ticker_items: []
    };
    try {
      deck = await createDeck(payload);
      decks = await fetchDecks();
    } catch {
      deck = { ...payload, id: `local-${Date.now()}` };
    }
    currentIndex = 0;
    broadcastToLive(true);
    flash('Novo ensaio criado.');
  }

  async function handleGenerateFromEvent(evId = selectedEventId) {
    if (!evId) return;
    try {
      deck = await createDeckFromEvent(evId);
      decks = await fetchDecks();
      currentIndex = 0;
      broadcastToLive(true);
      flash('✓ Ensaio gerado com capítulos e nuances a partir do Dossiê!');
    } catch {
      flash('⚠ Não foi possível gerar pelo servidor (verifique se a API está rodando).');
    }
  }

  async function handleGenerateLiveFeed() {
    try {
      deck = await createDeckFromLiveFeed({ limit: 10 });
      decks = await fetchDecks();
      currentIndex = 0;
      tickerOpen = true;
      broadcastToLive(true);
      flash('✓ Pauta de Giro Ao Vivo gerada com os últimos eventos!');
    } catch {
      flash('⚠ Não foi possível gerar giro ao vivo (verifique a API).');
    }
  }

  async function handleDeleteCurrentDeck() {
    if (!deck?.id) return;
    try {
      await deleteDeck(deck.id);
      decks = await fetchDecks();
      if (decks.length) {
        deck = await fetchDeck(decks[0].id);
      } else {
        deck = structuredClone(DEMO_FALLBACK_DECK);
      }
      currentIndex = 0;
      broadcastToLive(true);
      flash('Roteiro removido.');
    } catch {
      flash('Não foi possível excluir este roteiro.');
    }
  }

  function addSlide() {
    deck.slides = [...deck.slides, emptySlide(deck.slides.length + 1)];
    currentIndex = deck.slides.length - 1;
    broadcastToLive();
  }

  function duplicateSlide() {
    const copy = structuredClone(deck.slides[currentIndex]);
    copy.shortDate = `${(copy.shortDate || 'Cap').slice(0, 54)} (2)`;
    const next = [...deck.slides];
    next.splice(currentIndex + 1, 0, copy);
    deck.slides = next;
    currentIndex += 1;
    broadcastToLive();
  }

  function moveSlide(dir) {
    const target = currentIndex + dir;
    if (target < 0 || target >= deck.slides.length) return;
    const next = [...deck.slides];
    [next[currentIndex], next[target]] = [next[target], next[currentIndex]];
    deck.slides = next;
    currentIndex = target;
    broadcastToLive();
  }

  function removeSlide() {
    if (deck.slides.length <= 1) return;
    deck.slides = deck.slides.filter((_, i) => i !== currentIndex);
    currentIndex = Math.max(0, currentIndex - 1);
    broadcastToLive();
  }

  function addArticleAsSlide(art) {
    const num = deck.slides.length + 1;
    const newSlide = {
      shortDate: `${String(num).padStart(2, '0')}. ${art.veiculo.slice(0, 12)}`,
      timestamp: `${art.veiculo} // Coleta RSS`,
      title: art.titulo,
      summary: art.resumo || art.titulo,
      summary2: '',
      deep: '',
      code: `Fonte: ${art.veiculo}`,
      nuance_notes: `Analisar o enquadramento de ${art.veiculo}: quem ganha voz nesta manchete e o que fica fora do quadro?`,
      metricLabel: 'FONTE INCORPORADA',
      metricVal: art.veiculo.slice(0, 14),
      metricColor: 'var(--cyan)',
      metricSub: art.idioma?.toUpperCase() || 'PT',
      specs: [
        ['Veículo', art.veiculo],
        ['Autor', art.autor || 'Redação']
      ],
      links: [{ label: `Matéria em ${art.veiculo}`, url: art.url_canonica }]
    };
    deck.slides = [...deck.slides, newSlide];
    currentIndex = deck.slides.length - 1;
    activeTab = 'slides';
    broadcastToLive();
    flash(`Matéria de ${art.veiculo} adicionada como slide #${num}.`);
  }

  function attachArticleLinkToCurrent(art) {
    const s = deck.slides[currentIndex];
    s.links = [...(s.links || []), { label: `${art.veiculo} // ${art.titulo.slice(0, 36)}`, url: art.url_canonica }];
    deck.slides = [...deck.slides];
    broadcastToLive();
    flash(`Link anexado ao slide #${currentIndex + 1}.`);
  }

  function addSpecRow() {
    const s = deck.slides[currentIndex];
    s.specs = [...(s.specs || []), ['Chave', 'Valor']];
    deck.slides = [...deck.slides];
  }

  function removeSpecRow(i) {
    const s = deck.slides[currentIndex];
    s.specs = s.specs.filter((_, idx) => idx !== i);
    deck.slides = [...deck.slides];
  }

  function addLinkRow() {
    const s = deck.slides[currentIndex];
    s.links = [...(s.links || []), { label: 'Fonte // Referência', url: 'https://' }];
    deck.slides = [...deck.slides];
  }

  function removeLinkRow(i) {
    const s = deck.slides[currentIndex];
    s.links = s.links.filter((_, idx) => idx !== i);
    deck.slides = [...deck.slides];
  }

  function addKpi() {
    deck.kpis = [...(deck.kpis || []), { label: 'Indicador:', value: 'Valor', color: 'var(--amber)' }];
    broadcastToLive();
  }

  function addChartCard() {
    deck.charts = [
      ...(deck.charts || []),
      {
        title: `${(deck.charts?.length || 0) + 1}. Nova Composição`,
        subtitle: 'Descrição comparativa das grandezas:',
        rows: [
          { label: 'Item A', pct: 100, displayValue: '100', color: 'crimson' },
          { label: 'Item B', pct: 45, displayValue: '45', color: 'amber' }
        ],
        footerTitle: 'Síntese Analítica',
        footerText: 'Conclusão extraída dos números acima.'
      }
    ];
    broadcastToLive();
  }

  function handleWindowKeydown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      e.preventDefault();
      handleSave();
    }
  }

  $: activeSlide = deck?.slides?.[currentIndex] || null;
  $: if (deck && syncChannel && liveMirror) {
    broadcastToLive(false);
  }

  onMount(() => {
    syncChannel = createLiveSyncClient({
      onConnectionChange: (ok) => (wsConnected = ok)
    });
    initStudio();
  });

  onDestroy(() => {
    if (syncChannel) syncChannel.close();
  });
</script>

<svelte:head>
  <title>Modo Estúdio (Ensaios &amp; Nuances) — Contraponto</title>
</svelte:head>

<svelte:window on:keydown={handleWindowKeydown} />

<div class="min-h-screen bg-[#09090b] text-[#e8e8e3] font-mono flex flex-col">
  <!-- BARRA SUPERIOR DO ESTÚDIO -->
  <header class="border-b border-[#242422] bg-black px-4 py-3 flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-3">
      <a href="/" class="text-xs px-2.5 py-1.5 border border-[#2b2b2b] text-gray-300 hover:border-white">
        ← Início
      </a>
      <div>
        <span class="text-[10px] uppercase tracking-widest text-[#a6ff00] block">Estúdio de Roteiro, Nuances &amp; Direção</span>
        <strong class="text-sm text-white">CONTRAPONTO // MODO ESTÚDIO</strong>
      </div>

      <select
        value={deck?.id || ''}
        on:change={handleSelectDeck}
        class="bg-[#121216] border border-[#4a4a46] px-3 py-1.5 text-xs text-white max-w-xs"
      >
        {#each decks as d (d.id)}
          <option value={d.id}>[{d.modo.toUpperCase()}] {d.titulo}</option>
        {/each}
      </select>
    </div>

    <div class="flex flex-wrap items-center gap-2 text-xs">
      <div class="flex items-center gap-1 bg-[#121216] border border-[#2b2b2b] p-1">
        <select bind:value={selectedEventId} class="bg-black text-gray-200 px-2 py-1 text-[11px] max-w-[210px]">
          {#each events as ev (ev.id)}
            <option value={ev.id}>{ev.titulo_provisorio}</option>
          {/each}
        </select>
        <button
          type="button"
          on:click={() => handleGenerateFromEvent(selectedEventId)}
          class="px-2.5 py-1 bg-[#a6ff00] text-black font-bold hover:opacity-90"
          title="Cria capítulos e notas de nuance a partir deste Dossiê"
        >
          + Ensaio do Dossiê
        </button>
      </div>

      <button
        type="button"
        on:click={handleGenerateLiveFeed}
        class="px-3 py-1.5 bg-[#121216] border border-[#ff2a2a]/70 text-[#ff6b6b] hover:bg-[#ff2a2a] hover:text-white font-semibold"
      >
        + Giro Live (RSS)
      </button>

      <button
        type="button"
        on:click={handleNewBlankEssay}
        class="px-3 py-1.5 bg-[#121216] border border-[#4a4a46] hover:border-white"
      >
        + Em Branco
      </button>

      <button
        type="button"
        on:click={handleSave}
        class="px-3.5 py-1.5 bg-[#ff9900] text-black font-bold hover:bg-[#ffad33]"
      >
        Salvar [Ctrl+S]
      </button>

      {#if deck?.id && !deck.id.startsWith('local-')}
        <a
          href={getDeckExportHtmlUrl(deck.id)}
          class="px-3 py-1.5 bg-[#121216] border border-[#00e5ff]/60 text-[#00e5ff] hover:bg-[#00e5ff] hover:text-black"
          title="Exporta um arquivo .html único igual ao exemplo.html"
        >
          ↓ HTML
        </a>
      {/if}

      <a
        href={`/live?deck=${encodeURIComponent(deck?.id || '')}&clean=1`}
        target="_blank"
        rel="noopener"
        class="px-3.5 py-1.5 bg-[#9e1b1b] text-white font-bold border border-[#ff9900]/60 hover:bg-[#b82222]"
      >
        Abrir Tela OBS / Live ↗
      </a>
    </div>
  </header>

  {#if statusMsg}
    <div class="bg-[#141a0a] border-b border-[#a6ff00]/50 px-4 py-1.5 text-xs text-[#a6ff00]">
      {statusMsg}
    </div>
  {/if}

  <!-- ÁREA PRINCIPAL DIVIDIDA: EDITOR DE NUANCES (ESQUERDA) + PALCO AO VIVO (DIREITA) -->
  <div class="flex-1 grid grid-cols-1 xl:grid-cols-12 min-h-0">
    <!-- COLUNA ESQUERDA: EDITOR -->
    <section class="xl:col-span-5 border-r border-[#242422] bg-[#0b0b0d] p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-62px)]">
      <!-- Metadados gerais do Roteiro -->
      <div class="grid grid-cols-1 sm:grid-cols-4 gap-2">
        <div class="sm:col-span-3">
          <label for="deck-title" class="block text-[10px] uppercase text-gray-400 mb-1">Título do Ensaio / Pauta</label>
          <input
            id="deck-title"
            type="text"
            bind:value={deck.titulo}
            class="w-full bg-black border border-[#3a3a36] px-2.5 py-1.5 text-xs text-white focus:border-[#ff9900] focus:outline-none"
          />
        </div>
        <div>
          <label for="deck-mode" class="block text-[10px] uppercase text-gray-400 mb-1">Formato</label>
          <select
            id="deck-mode"
            bind:value={deck.modo}
            class="w-full bg-black border border-[#3a3a36] px-2 py-1.5 text-xs text-white"
          >
            <option value="ensaio">Ensaio</option>
            <option value="live">Live / Giro</option>
          </select>
        </div>
      </div>

      <!-- Abas do Estúdio -->
      <div class="flex flex-wrap gap-1 border-b border-[#242422] pb-2 text-[11px]">
        <button
          type="button"
          class="px-2.5 py-1 border {activeTab === 'slides' ? 'bg-white text-black font-bold border-white' : 'border-[#333] text-gray-300'}"
          on:click={() => (activeTab = 'slides')}
        >
          1. Capítulos &amp; Nuances ({deck.slides?.length || 0})
        </button>
        <button
          type="button"
          class="px-2.5 py-1 border {activeTab === 'kpis' ? 'bg-white text-black font-bold border-white' : 'border-[#333] text-gray-300'}"
          on:click={() => (activeTab = 'kpis')}
        >
          2. KPIs &amp; Ticker
        </button>
        <button
          type="button"
          class="px-2.5 py-1 border {activeTab === 'charts' ? 'bg-white text-black font-bold border-white' : 'border-[#333] text-gray-300'}"
          on:click={() => (activeTab = 'charts')}
        >
          3. Gráficos [G] ({deck.charts?.length || 0})
        </button>
        <button
          type="button"
          class="px-2.5 py-1 border {activeTab === 'rss' ? 'bg-white text-black font-bold border-white' : 'border-[#333] text-gray-300'}"
          on:click={() => (activeTab = 'rss')}
        >
          4. Banco RSS ({articles.length})
        </button>
      </div>

      {#if activeTab === 'slides' && activeSlide}
        <!-- Seletor e ordenação de capítulos -->
        <div class="space-y-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex flex-wrap gap-1">
              {#each deck.slides as s, idx}
                <button
                  type="button"
                  on:click={() => selectStudioSlide(idx)}
                  class="px-2 py-1 text-[11px] border {idx === currentIndex
                    ? 'bg-[#ff9900] text-black font-bold border-[#ff9900]'
                    : 'bg-[#121216] text-gray-300 border-[#333]'}"
                >
                  {s.shortDate}
                </button>
              {/each}
            </div>
            <div class="flex gap-1 text-[11px]">
              <button type="button" on:click={addSlide} class="px-2 py-1 bg-[#121216] border border-[#a6ff00] text-[#a6ff00]">+ Cap.</button>
              <button type="button" on:click={duplicateSlide} class="px-2 py-1 bg-[#121216] border border-[#444]" title="Duplicar">⧉</button>
              <button type="button" on:click={() => moveSlide(-1)} class="px-2 py-1 bg-[#121216] border border-[#444]" title="Mover p/ trás">←</button>
              <button type="button" on:click={() => moveSlide(1)} class="px-2 py-1 bg-[#121216] border border-[#444]" title="Mover p/ frente">→</button>
              <button type="button" on:click={removeSlide} class="px-2 py-1 bg-[#121216] border border-[#ff2a2a]/60 text-[#ff6b6b]" title="Remover slide">✕</button>
            </div>
          </div>

          <!-- BLOCO EM DESTAQUE: ROTEIRO DE ENSAIO & NUANCES + IA -->
          <div class="p-3 bg-[#10150a] border border-[#a6ff00]/50 space-y-2">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <label for="s-nuance" class="text-[10px] font-bold uppercase tracking-wider text-[#a6ff00]">
                ★ Nuances do Ensaio / Roteiro de Fala (Teleprompter do Apresentador)
              </label>
              <span class="text-[10px] text-gray-400">Oculto no OBS (`clean=1`)</span>
            </div>
            <textarea
              id="s-nuance"
              rows="3"
              bind:value={activeSlide.nuance_notes}
              on:input={() => (deck.slides = [...deck.slides])}
              placeholder="Escreva a sutileza argumentativa, o que comparar entre as fontes, ironias do vocabulário ou gancho para o próximo capítulo..."
              class="w-full bg-black/80 border border-[#a6ff00]/40 p-2 text-xs text-[#e8f8c8] focus:border-[#a6ff00] focus:outline-none"
            ></textarea>
            <div class="flex flex-wrap gap-1.5 items-center">
              <input
                type="text"
                bind:value={angleHint}
                placeholder="Ângulo p/ IA (opcional: ex. 'ironia sobre subsídios', 'tom didático', 'gancho histórico')"
                class="flex-1 min-w-[180px] bg-black border border-[#3a4a24] px-2 py-1 text-[11px] text-gray-200"
              />
              <button
                type="button"
                disabled={suggestingNuance}
                on:click={handleSuggestNuance}
                class="px-2.5 py-1 bg-[#a6ff00] text-black font-bold text-[11px] hover:opacity-90 disabled:opacity-50"
              >
                {suggestingNuance ? '⟳ Gerando no LLM...' : '✨ Sugerir Nuance c/ IA'}
              </button>
            </div>
          </div>

          <!-- Nó e Carimbo de Tempo -->
          <div class="grid grid-cols-2 gap-2">
            <div>
              <label for="s-short" class="block text-[10px] uppercase text-gray-400 mb-1">Rótulo na Timeline</label>
              <input
                id="s-short"
                type="text"
                bind:value={activeSlide.shortDate}
                on:input={() => (deck.slides = [...deck.slides])}
                class="w-full bg-black border border-[#333] px-2 py-1.5 text-xs text-white"
              />
            </div>
            <div>
              <label for="s-ts" class="block text-[10px] uppercase text-gray-400 mb-1">Subtítulo / Carimbo</label>
              <input
                id="s-ts"
                type="text"
                bind:value={activeSlide.timestamp}
                on:input={() => (deck.slides = [...deck.slides])}
                class="w-full bg-black border border-[#333] px-2 py-1.5 text-xs text-[#ff9900]"
              />
            </div>
          </div>

          <div>
            <label for="s-title" class="block text-[10px] uppercase text-gray-400 mb-1">Manchete Principal (Instrument Serif)</label>
            <textarea
              id="s-title"
              rows="2"
              bind:value={activeSlide.title}
              on:input={() => (deck.slides = [...deck.slides])}
              class="w-full bg-black border border-[#333] p-2 text-sm text-white font-serif"
            ></textarea>
          </div>

          <div>
            <label for="s-sum1" class="block text-[10px] uppercase text-gray-400 mb-1">Parágrafo 1 (Âncora / Fato)</label>
            <textarea
              id="s-sum1"
              rows="3"
              bind:value={activeSlide.summary}
              on:input={() => (deck.slides = [...deck.slides])}
              class="w-full bg-black border border-[#333] p-2 text-xs text-gray-200"
            ></textarea>
          </div>

          <div>
            <label for="s-sum2" class="block text-[10px] uppercase text-gray-400 mb-1">Parágrafo 2 (Tensão / Contraponto)</label>
            <textarea
              id="s-sum2"
              rows="3"
              bind:value={activeSlide.summary2}
              on:input={() => (deck.slides = [...deck.slides])}
              class="w-full bg-black border border-[#333] p-2 text-xs text-gray-300"
            ></textarea>
          </div>

          <!-- Gaveta [Espaço] -->
          <div class="p-3 bg-[#121216] border border-[#2b2b2b] space-y-2">
            <div class="text-[10px] uppercase tracking-wider text-[#ff9900] font-bold">Gaveta de Expansão [Tecla Espaço]</div>
            <textarea
              rows="3"
              bind:value={activeSlide.deep}
              on:input={() => (deck.slides = [...deck.slides])}
              placeholder="Aprofundamento histórico, técnico ou omissões estruturais..."
              class="w-full bg-black border border-[#333] p-2 text-xs text-gray-200"
            ></textarea>
            <input
              type="text"
              bind:value={activeSlide.code}
              on:input={() => (deck.slides = [...deck.slides])}
              placeholder="Citação verificada ou destaque em ciano..."
              class="w-full bg-black border border-[#333] px-2 py-1.5 text-xs text-[#00e5ff]"
            />
          </div>

          <!-- Coluna Direita do Slide (Indicador + Specs + Links) -->
          <div class="p-3 bg-[#121216] border border-[#2b2b2b] space-y-3">
            <div class="text-[10px] uppercase tracking-wider text-[#00e5ff] font-bold">Coluna Lateral (Telemetria &amp; Fontes)</div>
            <div class="grid grid-cols-3 gap-2">
              <div>
                <span class="block text-[10px] text-gray-400 mb-1">Rótulo</span>
                <input
                  type="text"
                  bind:value={activeSlide.metricLabel}
                  on:input={() => (deck.slides = [...deck.slides])}
                  class="w-full bg-black border border-[#333] px-2 py-1 text-xs"
                />
              </div>
              <div>
                <span class="block text-[10px] text-gray-400 mb-1">Número/Destaque</span>
                <input
                  type="text"
                  bind:value={activeSlide.metricVal}
                  on:input={() => (deck.slides = [...deck.slides])}
                  class="w-full bg-black border border-[#333] px-2 py-1 text-xs font-bold"
                />
              </div>
              <div>
                <span class="block text-[10px] text-gray-400 mb-1">Cor</span>
                <select
                  bind:value={activeSlide.metricColor}
                  on:change={() => (deck.slides = [...deck.slides])}
                  class="w-full bg-black border border-[#333] px-2 py-1 text-xs"
                >
                  {#each COLOR_PRESETS as c}
                    <option value={c.value}>{c.label}</option>
                  {/each}
                </select>
              </div>
            </div>
            <input
              type="text"
              bind:value={activeSlide.metricSub}
              on:input={() => (deck.slides = [...deck.slides])}
              placeholder="Legenda do indicador..."
              class="w-full bg-black border border-[#333] px-2 py-1 text-xs text-gray-300"
            />

            <!-- Lista de especificações -->
            <div class="space-y-1.5">
              <div class="flex justify-between items-center text-[10px] text-gray-400">
                <span>Linhas de Especificação</span>
                <button type="button" on:click={addSpecRow} class="text-[#ff9900] hover:underline">+ Linha</button>
              </div>
              {#each activeSlide.specs || [] as spec, sIdx}
                <div class="grid grid-cols-12 gap-1">
                  <input
                    type="text"
                    bind:value={spec[0]}
                    on:input={() => (deck.slides = [...deck.slides])}
                    class="col-span-5 bg-black border border-[#333] px-2 py-1 text-[11px]"
                  />
                  <input
                    type="text"
                    bind:value={spec[1]}
                    on:input={() => (deck.slides = [...deck.slides])}
                    class="col-span-6 bg-black border border-[#333] px-2 py-1 text-[11px]"
                  />
                  <button type="button" on:click={() => removeSpecRow(sIdx)} class="col-span-1 text-red-400">✕</button>
                </div>
              {/each}
            </div>

            <!-- Links -->
            <div class="space-y-1.5">
              <div class="flex justify-between items-center text-[10px] text-gray-400">
                <span>Links de Fontes</span>
                <button type="button" on:click={addLinkRow} class="text-[#00e5ff] hover:underline">+ Link</button>
              </div>
              {#each activeSlide.links || [] as lnk, lIdx}
                <div class="grid grid-cols-12 gap-1">
                  <input
                    type="text"
                    bind:value={lnk.label}
                    on:input={() => (deck.slides = [...deck.slides])}
                    placeholder="Veículo // Título"
                    class="col-span-5 bg-black border border-[#333] px-2 py-1 text-[11px]"
                  />
                  <input
                    type="text"
                    bind:value={lnk.url}
                    on:input={() => (deck.slides = [...deck.slides])}
                    placeholder="https://..."
                    class="col-span-6 bg-black border border-[#333] px-2 py-1 text-[11px]"
                  />
                  <button type="button" on:click={() => removeLinkRow(lIdx)} class="col-span-1 text-red-400">✕</button>
                </div>
              {/each}
            </div>
          </div>
        </div>
      {:else if activeTab === 'kpis'}
        <div class="space-y-4">
          <div class="space-y-2">
            <div class="flex justify-between items-center">
              <span class="text-xs font-bold text-white">Indicadores do Topo (KPIs)</span>
              <button type="button" on:click={addKpi} class="text-xs text-[#ff9900]">+ Adicionar KPI</button>
            </div>
            {#each deck.kpis || [] as kpi, kIdx}
              <div class="grid grid-cols-12 gap-1.5">
                <input
                  type="text"
                  bind:value={kpi.label}
                  on:input={() => (deck.kpis = [...deck.kpis])}
                  class="col-span-4 bg-black border border-[#333] px-2 py-1 text-xs"
                />
                <input
                  type="text"
                  bind:value={kpi.value}
                  on:input={() => (deck.kpis = [...deck.kpis])}
                  class="col-span-4 bg-black border border-[#333] px-2 py-1 text-xs font-bold"
                />
                <select
                  bind:value={kpi.color}
                  on:change={() => (deck.kpis = [...deck.kpis])}
                  class="col-span-3 bg-black border border-[#333] px-1.5 py-1 text-xs"
                >
                  {#each COLOR_PRESETS as c}
                    <option value={c.value}>{c.label}</option>
                  {/each}
                </select>
                <button
                  type="button"
                  on:click={() => (deck.kpis = deck.kpis.filter((_, i) => i !== kIdx))}
                  class="col-span-1 text-red-400"
                >
                  ✕
                </button>
              </div>
            {/each}
          </div>

          <div class="space-y-2 pt-3 border-t border-[#242422]">
            <span class="block text-xs font-bold text-white">Manchetes do Ticker Ao Vivo [Tecla T] (uma por linha)</span>
            <textarea
              rows="8"
              value={(deck.ticker_items || []).join('\n')}
              on:input={(e) => (deck.ticker_items = e.currentTarget.value.split('\n').map((s) => s.trim()).filter(Boolean))}
              placeholder="[Veículo] Manchete em destaque na faixa inferior..."
              class="w-full bg-black border border-[#333] p-2 text-xs text-gray-200"
            ></textarea>
          </div>

          <div class="pt-4 border-t border-[#242422]">
            <button
              type="button"
              on:click={handleDeleteCurrentDeck}
              class="px-3 py-1.5 border border-[#ff2a2a]/60 text-[#ff6b6b] text-xs hover:bg-[#ff2a2a] hover:text-white"
            >
              Excluir este roteiro permanentemente
            </button>
          </div>
        </div>
      {:else if activeTab === 'charts'}
        <div class="space-y-4">
          <div class="flex justify-between items-center">
            <span class="text-xs font-bold text-white">Painel de Composições Gráficas [Tecla G]</span>
            <button type="button" on:click={addChartCard} class="text-xs text-[#ff9900]">+ Card Gráfico</button>
          </div>

          {#each deck.charts || [] as card, cIdx}
            <div class="p-3 bg-[#121216] border border-[#2b2b2b] space-y-2">
              <div class="flex justify-between gap-2">
                <input
                  type="text"
                  bind:value={card.title}
                  on:input={() => (deck.charts = [...deck.charts])}
                  class="flex-1 bg-black border border-[#333] px-2 py-1 text-xs font-bold text-white"
                />
                <button
                  type="button"
                  on:click={() => (deck.charts = deck.charts.filter((_, i) => i !== cIdx))}
                  class="text-xs text-red-400 px-2"
                >
                  Remover
                </button>
              </div>
              <input
                type="text"
                bind:value={card.subtitle}
                on:input={() => (deck.charts = [...deck.charts])}
                placeholder="Subtítulo explicativo..."
                class="w-full bg-black border border-[#333] px-2 py-1 text-xs text-gray-300"
              />

              {#each card.rows || [] as r, rIdx}
                <div class="grid grid-cols-12 gap-1 items-center text-[11px]">
                  <input
                    type="text"
                    bind:value={r.label}
                    on:input={() => (deck.charts = [...deck.charts])}
                    class="col-span-4 bg-black border border-[#333] px-1.5 py-1"
                  />
                  <input
                    type="number"
                    min="0"
                    max="100"
                    bind:value={r.pct}
                    on:input={() => (deck.charts = [...deck.charts])}
                    class="col-span-2 bg-black border border-[#333] px-1.5 py-1"
                    title="Largura %"
                  />
                  <input
                    type="text"
                    bind:value={r.displayValue}
                    on:input={() => (deck.charts = [...deck.charts])}
                    class="col-span-3 bg-black border border-[#333] px-1.5 py-1"
                  />
                  <select
                    bind:value={r.color}
                    on:change={() => (deck.charts = [...deck.charts])}
                    class="col-span-2 bg-black border border-[#333] px-1 py-1"
                  >
                    <option value="crimson">Verm.</option>
                    <option value="amber">Âmbar</option>
                    <option value="cyan">Ciano</option>
                    <option value="dim">Cinza</option>
                  </select>
                  <button
                    type="button"
                    on:click={() => {
                      card.rows = card.rows.filter((_, i) => i !== rIdx);
                      deck.charts = [...deck.charts];
                    }}
                    class="col-span-1 text-red-400"
                  >
                    ✕
                  </button>
                </div>
              {/each}

              <button
                type="button"
                on:click={() => {
                  card.rows = [...(card.rows || []), { label: 'Novo', pct: 50, displayValue: '50', color: 'amber' }];
                  deck.charts = [...deck.charts];
                }}
                class="text-[11px] text-[#00e5ff] hover:underline"
              >
                + Barra comparativa
              </button>

              <div class="grid grid-cols-2 gap-1.5 pt-1">
                <input
                  type="text"
                  bind:value={card.footerTitle}
                  on:input={() => (deck.charts = [...deck.charts])}
                  placeholder="Título rodapé"
                  class="bg-black border border-[#333] px-2 py-1 text-[11px] text-[#ff9900]"
                />
                <input
                  type="text"
                  bind:value={card.footerText}
                  on:input={() => (deck.charts = [...deck.charts])}
                  placeholder="Nota final do card"
                  class="bg-black border border-[#333] px-2 py-1 text-[11px]"
                />
              </div>
            </div>
          {/each}
        </div>
      {:else if activeTab === 'rss'}
        <div class="space-y-2.5">
          <p class="text-[11px] text-gray-400">
            Puxe qualquer matéria coletada pelo agregador diretamente para o seu ensaio ou pauta ao vivo:
          </p>
          {#each articles as art (art.id)}
            <div class="p-3 bg-[#121216] border border-[#2b2b2b] space-y-2">
              <div class="text-[10px] text-[#ff9900] uppercase">{art.veiculo}</div>
              <div class="text-xs font-semibold text-white">{art.titulo}</div>
              {#if art.resumo}
                <p class="text-[11px] text-gray-400 line-clamp-2">{art.resumo}</p>
              {/if}
              <div class="flex gap-2 pt-1">
                <button
                  type="button"
                  on:click={() => addArticleAsSlide(art)}
                  class="px-2.5 py-1 bg-[#a6ff00] text-black font-bold text-[11px]"
                >
                  + Virar Novo Slide
                </button>
                <button
                  type="button"
                  on:click={() => attachArticleLinkToCurrent(art)}
                  class="px-2.5 py-1 border border-[#4a4a46] text-[11px] text-gray-200 hover:border-white"
                >
                  + Anexar Link ao Slide Atual
                </button>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </section>

    <!-- COLUNA DIREITA: MONITOR DE RETORNO & DIRETORA AO VIVO -->
    <section class="xl:col-span-7 bg-[#050505] p-4 flex flex-col gap-3 min-h-[680px]">
      <div class="flex flex-wrap items-center justify-between gap-2 text-xs bg-[#0b0b0d] border border-[#242422] px-3 py-2">
        <div class="flex items-center gap-3">
          <span class="inline-flex items-center gap-1.5 font-bold text-[#a6ff00]">
            <span class="w-2 h-2 rounded-full bg-[#a6ff00]"></span>
            MONITOR DE ESTÚDIO / DIREÇÃO
          </span>
          <label class="inline-flex items-center gap-1.5 text-gray-300 cursor-pointer">
            <input type="checkbox" bind:checked={liveMirror} />
            <span>Sincronizar ao vivo</span>
          </label>
          <span class="text-[10px] px-2 py-0.5 border {wsConnected ? 'border-[#00e5ff] text-[#00e5ff]' : 'border-[#444] text-gray-400'}">
            {wsConnected ? '● WebSocket OBS Ativo' : '○ Canal Local (mesmo navegador)'}
          </span>
        </div>
        <span class="text-[11px] text-gray-400">
          Clique nos nós ou botões abaixo para operar a transmissão remotamente
        </span>
      </div>

      <div class="flex-1 min-h-0">
        <BroadcastStage
          {deck}
          bind:currentIndex
          bind:drawerOpen
          bind:chartsOpen
          bind:webcamOpen
          bind:tickerOpen
          bind:nuanceOpen
          embedded={true}
          on:change={() => broadcastToLive(false)}
          on:state={() => broadcastToLive(false)}
        />
      </div>
    </section>
  </div>
</div>
