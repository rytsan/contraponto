<script>
  import { onDestroy, onMount, tick } from 'svelte';
  import ActorGraph from './ActorGraph.svelte';

  export let dossier;

  let activeMode = 'graph'; // 'graph' | 'map'
  let mapContainer;
  let leafletMap = null;
  let selectedCoverageIndex = 0;

  $: coordinates = dossier?.coordinates || { lat: null, lon: null };
  $: hasCoordinates =
    coordinates &&
    coordinates.lat !== null &&
    coordinates.lat !== undefined &&
    coordinates.lon !== null &&
    coordinates.lon !== undefined &&
    !Number.isNaN(Number(coordinates.lat)) &&
    !Number.isNaN(Number(coordinates.lon));

  $: coveragePairs = dossier?.coverage_pairs || [];
  $: actors = dossier?.actors || [];

  async function initLeafletMap() {
    if (!hasCoordinates || !mapContainer) return;
    const LModule = await import('leaflet');
    const L = LModule.default || LModule;

    if (leafletMap) {
      leafletMap.remove();
      leafletMap = null;
    }

    const lat = Number(coordinates.lat);
    const lon = Number(coordinates.lon);

    leafletMap = L.map(mapContainer).setView([lat, lon], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18
    }).addTo(leafletMap);

    // Marcador central do evento e marcadores deslocados levemente por cobertura para clique individual
    coveragePairs.forEach((pair, idx) => {
      const offsetLat = lat + (idx - 1) * 0.008;
      const offsetLon = lon + (idx - 1) * 0.008;
      const firstVerifiedQuote =
        (pair.evidence_quotes || []).find((q) => q.verified)?.quote ||
        pair.central_thesis ||
        '';

      const circleMarker = L.circleMarker([offsetLat, offsetLon], {
        radius: 10,
        fillColor: idx === 0 ? '#9e1b1b' : idx === 1 ? '#e5a93c' : '#3b82f6',
        color: '#f4f1ea',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
      }).addTo(leafletMap);

      circleMarker.bindPopup(
        `<div style="color:#111;max-width:260px;font-family:sans-serif;">
          <strong>${pair.source}</strong><br/>
          <em>${pair.headline}</em><br/><br/>
          <small>“${firstVerifiedQuote.slice(0, 140)}...”</small><br/>
          <a href="${pair.url}" target="_blank" rel="noopener">Abrir matéria original ↗</a>
        </div>`
      );

      circleMarker.on('click', () => {
        selectedCoverageIndex = idx;
      });
    });
  }

  async function switchMode(mode) {
    activeMode = mode;
    if (mode === 'map' && hasCoordinates) {
      await tick();
      await initLeafletMap();
    }
  }

  onMount(() => {
    // Se não houver coordenadas válidas, mantém foco obrigatório no Grafo de Atores
    activeMode = 'graph';
  });

  onDestroy(() => {
    if (leafletMap) {
      leafletMap.remove();
      leafletMap = null;
    }
  });
</script>

<svelte:head>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    crossorigin=""
  />
</svelte:head>

<section aria-labelledby="scene-3-heading" class="space-y-6 py-2">
  <!-- Cabeçalho e Alternador entre Grafo de Atores e Mapa Geográfico -->
  <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#2b2b2b] pb-4">
    <div class="space-y-1">
      <span class="px-2.5 py-1 rounded font-mono text-xs bg-[#9e1b1b]/25 text-[#f4f1ea] border border-[#9e1b1b]">
        CENA 03 // MAPA DE PODER E RELAÇÕES
      </span>
      <h2 id="scene-3-heading" class="font-serif text-2xl sm:text-3xl font-bold text-[#f4f1ea] pt-1">
        Arquitetura Material de Atores, Território e Interesses
      </h2>
    </div>

    <div class="inline-flex rounded-lg p-1 bg-[#161616] border border-[#2b2b2b] self-start">
      <button
        type="button"
        on:click={() => switchMode('graph')}
        class="px-4 py-2 rounded font-mono text-xs uppercase tracking-wider scene-transition {activeMode ===
        'graph'
          ? 'bg-[#9e1b1b] text-[#f4f1ea] font-bold'
          : 'text-gray-400 hover:text-[#f4f1ea]'}"
      >
        🕸️ Grafo de Atores (Cytoscape.js)
      </button>
      <button
        type="button"
        on:click={() => switchMode('map')}
        class="px-4 py-2 rounded font-mono text-xs uppercase tracking-wider scene-transition {activeMode ===
        'map'
          ? 'bg-[#9e1b1b] text-[#f4f1ea] font-bold'
          : 'text-gray-400 hover:text-[#f4f1ea]'}"
      >
        🗺️ Mapa Geográfico (Leaflet)
      </button>
    </div>
  </div>

  {#if !hasCoordinates}
    <div class="p-4 rounded bg-[#161616] border border-[#e5a93c]/50 flex items-center justify-between gap-4 text-xs font-mono text-gray-300">
      <span>
        ⚠️ <strong>Aviso de Geolocalização:</strong> Este acontecimento não possui coordenadas geográficas precisas verificadas (Nominatim). O Contraponto jamais inventa coordenadas via LLM; o foco permanece no Grafo de Atores.
      </span>
      {#if activeMode === 'map'}
        <button
          type="button"
          on:click={() => switchMode('graph')}
          class="px-3 py-1.5 rounded bg-[#9e1b1b] text-[#f4f1ea] shrink-0"
        >
          Voltar ao Grafo de Atores
        </button>
      {/if}
    </div>
  {/if}

  {#if activeMode === 'graph' || !hasCoordinates}
    <ActorGraph {actors} {coveragePairs} />
  {:else}
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <div class="lg:col-span-8 bg-[#161616] border border-[#2b2b2b] rounded-lg p-4 space-y-3">
        <div class="flex items-center justify-between font-mono text-xs text-gray-300">
          <span>📍 Local verificado: <strong class="text-[#e5a93c]">{dossier?.location}</strong></span>
          <span>Lat: {Number(coordinates.lat).toFixed(4)} | Lon: {Number(coordinates.lon).toFixed(4)}</span>
        </div>
        <div
          bind:this={mapContainer}
          class="w-full h-[420px] rounded border border-[#2b2b2b] bg-[#0d0d0d] z-10"
          aria-label="Mapa geográfico OpenStreetMap do evento"
        ></div>
      </div>

      <aside class="lg:col-span-4 bg-[#161616] border border-[#2b2b2b] rounded-lg p-5 space-y-4">
        <h3 class="font-mono text-xs uppercase tracking-wider text-[#e5a93c] font-bold">
          Marcadores de Cobertura no Território
        </h3>
        <div class="space-y-3">
          {#each coveragePairs as pair, idx}
            {@const verifiedQuote = (pair.evidence_quotes || []).find((q) => q.verified)}
            <div
              class="p-3.5 rounded border scene-transition cursor-pointer {selectedCoverageIndex === idx
                ? 'bg-[#1d1d1d] border-[#e5a93c]'
                : 'bg-[#121212] border-[#2b2b2b]'}"
              on:click={() => (selectedCoverageIndex = idx)}
              on:keydown={(e) => e.key === 'Enter' && (selectedCoverageIndex = idx)}
              role="button"
              tabindex="0"
            >
              <div class="flex items-center justify-between gap-2 mb-1">
                <span class="font-mono text-xs font-bold text-[#e5a93c]">{pair.source}</span>
                <a
                  href={pair.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="font-mono text-[11px] text-gray-400 hover:text-[#f4f1ea]"
                >
                  Link ↗
                </a>
              </div>
              <p class="font-serif text-sm font-semibold text-[#f4f1ea] mb-1.5">{pair.headline}</p>
              <p class="text-xs text-gray-300 mb-2">{pair.central_thesis}</p>
              {#if verifiedQuote}
                <p class="font-serif italic text-xs text-gray-400 border-l-2 border-[#9e1b1b] pl-2">
                  “{verifiedQuote.quote}”
                </p>
              {/if}
            </div>
          {/each}
        </div>
      </aside>
    </div>
  {/if}
</section>
