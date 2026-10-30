<script>
  import { onDestroy, onMount } from 'svelte';
  import { page } from '$app/stores';
  import BroadcastStage from '$lib/components/BroadcastStage.svelte';
  import {
    DEMO_FALLBACK_DECK,
    createDeckFromLiveFeed,
    createLiveSyncClient,
    fetchDeck,
    fetchDecks,
    triggerCollectNow
  } from '$lib/api.js';

  let deck = DEMO_FALLBACK_DECK;
  let decksList = [];
  let currentIndex = 0;
  let drawerOpen = false;
  let chartsOpen = false;
  let webcamOpen = false;
  let tickerOpen = false;
  let nuanceOpen = false;
  let cleanObs = false;
  let pautaOpen = false;
  let busyMsg = '';
  let syncChannel = null;

  async function initLive() {
    const params = $page.url.searchParams;
    const requestedId = params.get('deck');
    cleanObs = params.get('clean') === '1';
    if (params.get('ticker') === '1') tickerOpen = true;

    decksList = await fetchDecks();
    if (requestedId) {
      deck = await fetchDeck(requestedId);
    } else {
      const liveSaved = decksList.find((d) => d.modo === 'live') || decksList[0];
      if (liveSaved) {
        deck = await fetchDeck(liveSaved.id);
      }
    }
    if (deck?.modo === 'live' && deck?.ticker_items?.length && params.get('ticker') !== '0') {
      tickerOpen = true;
    }
  }

  async function switchDeck(id) {
    deck = await fetchDeck(id);
    currentIndex = 0;
    drawerOpen = false;
    pautaOpen = false;
  }

  async function handleCollectAndRefreshLive() {
    busyMsg = 'Coletando feeds RSS e agrupando pautas...';
    try {
      await triggerCollectNow();
      deck = await createDeckFromLiveFeed({ limit: 10 });
      decksList = await fetchDecks();
      currentIndex = 0;
      tickerOpen = true;
      pautaOpen = false;
    } catch {
      try {
        deck = await createDeckFromLiveFeed({ limit: 10 });
        decksList = await fetchDecks();
        currentIndex = 0;
        pautaOpen = false;
      } catch {
        busyMsg = 'API offline — mantendo pauta local.';
        setTimeout(() => (busyMsg = ''), 2500);
        return;
      }
    }
    busyMsg = '';
  }

  async function handleBuildLiveOnly() {
    busyMsg = 'Montando giro ao vivo com os últimos eventos...';
    try {
      deck = await createDeckFromLiveFeed({ limit: 10 });
      decksList = await fetchDecks();
      currentIndex = 0;
      tickerOpen = true;
      pautaOpen = false;
    } catch {
      busyMsg = 'Não foi possível gerar giro (verifique a API).';
      setTimeout(() => (busyMsg = ''), 2500);
      return;
    }
    busyMsg = '';
  }

  function handleKeydown(e) {
    if (e.target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
    const maxIdx = Math.max(0, (deck?.slides?.length || 1) - 1);
    if (e.key === 'ArrowRight') {
      currentIndex = Math.min(maxIdx, currentIndex + 1);
    } else if (e.key === 'ArrowLeft') {
      currentIndex = Math.max(0, currentIndex - 1);
    } else if (e.key === ' ' || e.key.toLowerCase() === 'e') {
      e.preventDefault();
      drawerOpen = !drawerOpen;
    } else if (e.key.toLowerCase() === 'g') {
      chartsOpen = !chartsOpen;
    } else if (e.key.toLowerCase() === 'c') {
      webcamOpen = !webcamOpen;
    } else if (e.key.toLowerCase() === 't') {
      tickerOpen = !tickerOpen;
    } else if (e.key.toLowerCase() === 'n') {
      nuanceOpen = !nuanceOpen;
    } else if (e.key.toLowerCase() === 'o') {
      cleanObs = !cleanObs;
    } else if (e.key.toLowerCase() === 'p') {
      pautaOpen = !pautaOpen;
    }
  }

  onMount(() => {
    initLive();
    syncChannel = createLiveSyncClient({
      onMessage(msg) {
        if (msg.type === 'SYNC_STATE') {
          if (msg.deck && (!deck?.id || msg.deck.id === deck.id || msg.forceDeck)) {
            deck = msg.deck;
          }
          if (typeof msg.currentIndex === 'number') currentIndex = msg.currentIndex;
          if (typeof msg.drawerOpen === 'boolean') drawerOpen = msg.drawerOpen;
          if (typeof msg.chartsOpen === 'boolean') chartsOpen = msg.chartsOpen;
          if (typeof msg.webcamOpen === 'boolean') webcamOpen = msg.webcamOpen;
          if (typeof msg.tickerOpen === 'boolean') tickerOpen = msg.tickerOpen;
        }
      }
    });
  });

  onDestroy(() => {
    if (syncChannel) syncChannel.close();
  });
</script>

<svelte:head>
  <title>{deck?.titulo || 'Modo Live'} — Contraponto Live</title>
</svelte:head>

<svelte:window on:keydown={handleKeydown} />

<BroadcastStage
  {deck}
  bind:currentIndex
  bind:drawerOpen
  bind:chartsOpen
  bind:webcamOpen
  bind:tickerOpen
  bind:nuanceOpen
  bind:cleanObs
  showPautaBtn={true}
  on:openPauta={() => (pautaOpen = !pautaOpen)}
/>

{#if pautaOpen}
  <div class="fixed inset-0 z-50 bg-black/80 flex justify-end font-mono text-xs">
    <div class="w-full max-w-md bg-[#0b0b0d] border-l border-[#4a4a46] p-6 flex flex-col justify-between overflow-y-auto">
      <div class="space-y-5">
        <div class="flex items-center justify-between border-b border-[#242422] pb-3">
          <strong class="text-sm text-white uppercase tracking-wider">Controle de Pauta &amp; Giro RSS</strong>
          <button
            type="button"
            class="px-2.5 py-1 border border-[#4a4a46] text-gray-300 hover:bg-white hover:text-black"
            on:click={() => (pautaOpen = false)}
          >
            Fechar [P]
          </button>
        </div>

        {#if busyMsg}
          <div class="p-3 bg-[#1a1405] border border-[#ff9900] text-[#ff9900]">{busyMsg}</div>
        {/if}

        <div class="grid grid-cols-1 gap-2.5">
          <button
            type="button"
            on:click={handleCollectAndRefreshLive}
            class="px-4 py-2.5 bg-[#9e1b1b] text-white font-bold border border-[#ff9900]/60 hover:bg-[#b82222] text-left"
          >
            ↻ Coletar RSS Agora + Gerar Giro Ao Vivo
          </button>
          <button
            type="button"
            on:click={handleBuildLiveOnly}
            class="px-4 py-2.5 bg-[#121216] text-white border border-[#4a4a46] hover:border-white text-left"
          >
            ⚡ Montar Giro com Eventos Já no Banco (10 Nós)
          </button>
          <a
            href={`/studio?deck=${encodeURIComponent(deck?.id || '')}`}
            class="px-4 py-2.5 bg-[#121216] text-[#a6ff00] border border-[#a6ff00]/50 hover:bg-[#1a220e] block"
          >
            ✎ Abrir Roteiro Atual no Modo Estúdio (Editar Nuances)
          </a>
        </div>

        <div class="space-y-2 pt-2 border-t border-[#242422]">
          <div class="text-[11px] uppercase tracking-wider text-gray-400">Ensaios &amp; Pautas Salvas</div>
          {#each decksList as d (d.id)}
            <button
              type="button"
              on:click={() => switchDeck(d.id)}
              class="w-full text-left p-3 border transition {d.id === deck?.id
                ? 'border-[#ff9900] bg-[#16130b] text-white'
                : 'border-[#242422] bg-[#121216] text-gray-300 hover:border-[#4a4a46]'}"
            >
              <div class="flex items-center justify-between gap-2 mb-1">
                <span class="uppercase text-[10px] px-1.5 py-0.5 border {d.modo === 'live' ? 'border-[#ff2a2a] text-[#ff2a2a]' : 'border-[#a6ff00] text-[#a6ff00]'}">
                  {d.modo}
                </span>
                <span class="text-[10px] text-gray-500">{d.slides_count} slides</span>
              </div>
              <div class="font-semibold truncate">{d.titulo}</div>
            </button>
          {/each}
        </div>
      </div>

      <div class="pt-4 border-t border-[#242422] flex justify-between items-center text-gray-400">
        <a href="/" class="hover:text-white">← Voltar ao Contraponto</a>
        <span>URL OBS: <code>?deck={deck?.id?.slice(0, 8)}&amp;clean=1</code></span>
      </div>
    </div>
  </div>
{/if}
