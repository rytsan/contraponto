<script>
  import { onDestroy, onMount } from 'svelte';

  export let actors = [];
  export let coveragePairs = [];

  let cyContainer;
  let cyInstance = null;
  let selectedActor = null;

  const TYPE_COLORS = {
    trabalhador: '#e5a93c',
    sindicato: '#d97706',
    movimento_popular: '#10b981',
    empresa: '#9e1b1b',
    estado: '#3b82f6',
    veiculo: '#8b5cf6',
    instituicao: '#6366f1',
    outro: '#6b7280'
  };

  const TYPE_LABELS = {
    trabalhador: 'Trabalhador / Categoria',
    sindicato: 'Sindicato',
    movimento_popular: 'Movimento Popular',
    empresa: 'Empresa / Capital',
    estado: 'Estado / Aparato Público',
    veiculo: 'Veículo de Mídia',
    instituicao: 'Instituição',
    outro: 'Outro Ator'
  };

  $: if (actors && actors.length > 0 && !selectedActor) {
    selectedActor = actors[0];
  }

  function findActorAppearances(actorName) {
    if (!actorName || !coveragePairs) return [];
    const needle = actorName.toLowerCase();
    const shortTokens = needle
      .split(/\s+/)
      .filter((w) => w.length > 4 && !['sindicato', 'movimento', 'consorcio', 'consórcio'].includes(w));

    const matches = [];
    for (const pair of coveragePairs) {
      const inValued = (pair.valued_actors || []).some(
        (a) => a.toLowerCase().includes(needle) || needle.includes(a.toLowerCase())
      );
      const inDevalued = (pair.devalued_actors || []).some(
        (a) => a.toLowerCase().includes(needle) || needle.includes(a.toLowerCase())
      );
      const matchingQuotes = (pair.evidence_quotes || []).filter((eq) => {
        const qLower = (eq.quote || '').toLowerCase();
        if (qLower.includes(needle)) return true;
        return shortTokens.some((tok) => qLower.includes(tok));
      });

      if (inValued || inDevalued || matchingQuotes.length > 0) {
        matches.push({
          article_id: pair.article_id,
          source: pair.source,
          url: pair.url,
          headline: pair.headline,
          framingRole: inValued
            ? 'Valorizado como sujeito'
            : inDevalued
              ? 'Desvalorizado / enquadrado como problema'
              : 'Mencionado nas evidências',
          quotes: matchingQuotes
        });
      }
    }
    return matches;
  }

  function findIncomingRelations(actorName) {
    if (!actorName || !actors) return [];
    const incoming = [];
    for (const act of actors) {
      for (const rel of act.relations || []) {
        if (rel.target === actorName) {
          incoming.push({
            source: act.name,
            relation: rel.relation,
            evidence: rel.evidence
          });
        }
      }
    }
    return incoming;
  }

  function selectActorByName(name) {
    const found = (actors || []).find((a) => a.name === name);
    if (found) {
      selectedActor = found;
    } else {
      selectedActor = {
        name,
        type: 'outro',
        role: 'Ator referenciado em relação direcionada',
        material_interest: 'sem_evidencia_suficiente',
        relations: []
      };
    }
  }

  async function initCytoscape() {
    if (!cyContainer || !actors || actors.length === 0) return;
    const cytoscapeModule = await import('cytoscape');
    const cytoscape = cytoscapeModule.default || cytoscapeModule;

    const elements = [];
    const nodeNames = new Set();

    for (const actor of actors) {
      nodeNames.add(actor.name);
      elements.push({
        data: {
          id: actor.name,
          label: actor.name,
          type: actor.type || 'outro',
          color: TYPE_COLORS[actor.type] || TYPE_COLORS.outro
        }
      });
    }

    for (const actor of actors) {
      for (const rel of actor.relations || []) {
        if (!nodeNames.has(rel.target)) {
          nodeNames.add(rel.target);
          elements.push({
            data: {
              id: rel.target,
              label: rel.target,
              type: 'outro',
              color: TYPE_COLORS.outro
            }
          });
        }
        elements.push({
          data: {
            id: `${actor.name}__${rel.relation}__${rel.target}`,
            source: actor.name,
            target: rel.target,
            label: rel.relation,
            evidence: rel.evidence
          }
        });
      }
    }

    if (cyInstance) {
      cyInstance.destroy();
    }

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    cyInstance = cytoscape({
      container: cyContainer,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            label: 'data(label)',
            color: '#f4f1ea',
            'font-size': '11px',
            'font-family': 'Inter, sans-serif',
            'text-wrap': 'wrap',
            'text-max-width': '130px',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            width: 34,
            height: 34,
            'border-width': 2,
            'border-color': '#f4f1ea'
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 4,
            'border-color': '#e5a93c',
            width: 42,
            height: 42
          }
        },
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': '#52525b',
            'target-arrow-color': '#e5a93c',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(label)',
            color: '#e5a93c',
            'font-size': '10px',
            'font-family': 'monospace',
            'text-background-color': '#0d0d0d',
            'text-background-opacity': 0.85,
            'text-background-padding': '3px'
          }
        }
      ],
      layout: {
        name: 'circle',
        padding: 36,
        animate: !prefersReducedMotion
      }
    });

    cyInstance.on('tap', 'node', (evt) => {
      const nodeId = evt.target.id();
      selectActorByName(nodeId);
    });
  }

  onMount(() => {
    initCytoscape();
  });

  onDestroy(() => {
    if (cyInstance) {
      cyInstance.destroy();
      cyInstance = null;
    }
  });
</script>

<div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
  <!-- Área do Grafo Cytoscape.js -->
  <div class="lg:col-span-7 bg-[#161616] border border-[#2b2b2b] rounded-lg p-4 space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-2 border-b border-[#2b2b2b] pb-3">
      <div>
        <h3 class="font-mono text-xs uppercase tracking-wider text-[#e5a93c] font-bold">
          Grafo de Atores e Relações de Poder (Cytoscape.js)
        </h3>
        <p class="text-xs text-gray-400">
          Clique em qualquer nó no grafo ou na barra abaixo para inspecionar interesses materiais e evidências.
        </p>
      </div>
      <button
        type="button"
        on:click={() => cyInstance && cyInstance.fit()}
        class="px-2.5 py-1 text-xs font-mono rounded bg-[#1d1d1d] border border-[#2b2b2b] text-gray-300 hover:border-[#e5a93c]"
      >
        Centralizar grafo
      </button>
    </div>

    {#if actors && actors.length > 0}
      <div
        bind:this={cyContainer}
        class="w-full h-[380px] sm:h-[440px] bg-[#0d0d0d] rounded border border-[#2b2b2b]"
        aria-label="Grafo interativo de atores em Cytoscape.js"
      ></div>

      <!-- Seletor rápido acessível de nós -->
      <div class="space-y-1.5">
        <span class="block font-mono text-[10px] uppercase tracking-wider text-gray-400">
          Atores mapeados ({actors.length}):
        </span>
        <div class="flex flex-wrap gap-1.5">
          {#each actors as act}
            <button
              type="button"
              on:click={() => (selectedActor = act)}
              class="px-2.5 py-1 rounded text-xs font-mono border scene-transition {selectedActor?.name ===
              act.name
                ? 'bg-[#9e1b1b] text-[#f4f1ea] border-[#e5a93c]'
                : 'bg-[#121212] text-gray-300 border-[#2b2b2b] hover:border-[#e5a93c]/60'}"
            >
              {act.name}
            </button>
          {/each}
        </div>
      </div>
    {:else}
      <div class="p-10 text-center font-mono text-xs text-gray-400">
        Sem evidência suficiente para construir o grafo de atores neste evento.
      </div>
    {/if}
  </div>

  <!-- Painel Lateral de Inspeção do Ator Selecionado -->
  <aside class="lg:col-span-5 bg-[#161616] border border-[#2b2b2b] rounded-lg p-5 space-y-5">
    {#if selectedActor}
      {@const appearances = findActorAppearances(selectedActor.name)}
      {@const incomingRels = findIncomingRelations(selectedActor.name)}

      <div class="border-b border-[#2b2b2b] pb-3 space-y-1.5">
        <span
          class="inline-block px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider bg-[#1d1d1d] text-[#e5a93c] border border-[#2b2b2b]"
        >
          {TYPE_LABELS[selectedActor.type] || selectedActor.type}
        </span>
        <h4 class="font-serif text-xl font-bold text-[#f4f1ea]">
          {selectedActor.name}
        </h4>
      </div>

      <div class="space-y-3 text-xs">
        <div class="p-3 rounded bg-[#0d0d0d] border border-[#2b2b2b]">
          <span class="block font-mono text-[10px] uppercase text-gray-400 mb-1">
            Papel Social no Evento
          </span>
          <p class="text-gray-200 leading-relaxed">
            {selectedActor.role === 'sem_evidencia_suficiente'
              ? 'Sem evidência suficiente nas matérias.'
              : selectedActor.role}
          </p>
        </div>

        <div class="p-3 rounded bg-[#0d0d0d] border border-[#9e1b1b]/50">
          <span class="block font-mono text-[10px] uppercase text-[#e5a93c] mb-1">
            Interesses Materiais e de Classe
          </span>
          <p class="text-gray-200 leading-relaxed">
            {selectedActor.material_interest === 'sem_evidencia_suficiente'
              ? 'Sem evidência suficiente nas matérias.'
              : selectedActor.material_interest}
          </p>
        </div>
      </div>

      <!-- Relações direcionadas (saída e entrada) -->
      <div class="space-y-2">
        <h5 class="font-mono text-xs uppercase tracking-wider text-[#e5a93c]">
          Relações Mapeadas
        </h5>
        {#if (selectedActor.relations && selectedActor.relations.length > 0) || incomingRels.length > 0}
          <ul class="space-y-2 text-xs">
            {#each selectedActor.relations || [] as rel}
              <li class="p-2.5 rounded bg-[#121212] border border-[#2b2b2b] space-y-1">
                <div class="font-mono flex items-center flex-wrap gap-1.5">
                  <span class="text-[#f4f1ea] font-semibold">{selectedActor.name}</span>
                  <span class="px-1.5 py-0.5 rounded bg-[#9e1b1b] text-[#f4f1ea] text-[10px] uppercase">
                    {rel.relation}
                  </span>
                  <button
                    type="button"
                    on:click={() => selectActorByName(rel.target)}
                    class="text-[#e5a93c] hover:underline font-semibold"
                  >
                    → {rel.target}
                  </button>
                </div>
                <p class="text-gray-400 leading-snug">{rel.evidence}</p>
              </li>
            {/each}

            {#each incomingRels as inc}
              <li class="p-2.5 rounded bg-[#121212] border border-[#2b2b2b] space-y-1">
                <div class="font-mono flex items-center flex-wrap gap-1.5">
                  <button
                    type="button"
                    on:click={() => selectActorByName(inc.source)}
                    class="text-[#e5a93c] hover:underline font-semibold"
                  >
                    {inc.source}
                  </button>
                  <span class="px-1.5 py-0.5 rounded bg-[#1d1d1d] border border-[#e5a93c]/50 text-[#e5a93c] text-[10px] uppercase">
                    {inc.relation}
                  </span>
                  <span class="text-[#f4f1ea] font-semibold">→ {selectedActor.name}</span>
                </div>
                <p class="text-gray-400 leading-snug">{inc.evidence}</p>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="text-xs text-gray-500 italic">Nenhuma aresta direta registrada para este nó.</p>
        {/if}
      </div>

      <!-- Aparições nas matérias e trechos de evidência -->
      <div class="space-y-2 pt-2 border-t border-[#2b2b2b]">
        <h5 class="font-mono text-xs uppercase tracking-wider text-[#e5a93c]">
          Aparições nas Matérias e Evidências ({appearances.length})
        </h5>
        {#if appearances.length > 0}
          <div class="space-y-2.5 max-h-60 overflow-y-auto pr-1">
            {#each appearances as appItem}
              <div class="p-3 rounded bg-[#121212] border border-[#2b2b2b] space-y-1.5 text-xs">
                <div class="flex items-center justify-between gap-2">
                  <span class="font-mono font-bold text-[#f4f1ea]">{appItem.source}</span>
                  <a
                    href={appItem.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="font-mono text-[11px] text-[#e5a93c] hover:underline shrink-0"
                  >
                    Matéria ↗
                  </a>
                </div>
                <p class="font-mono text-[11px] text-gray-400">{appItem.framingRole}</p>
                {#each appItem.quotes as q}
                  <p class="font-serif italic text-gray-300 border-l-2 border-[#e5a93c] pl-2">
                    “{q.quote}”
                  </p>
                {/each}
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-xs text-gray-500 italic">
            Ator estrutural sintetizado na consolidação do evento.
          </p>
        {/if}
      </div>
    {:else}
      <p class="text-xs font-mono text-gray-400">
        Selecione um nó no grafo ao lado para inspecionar seus interesses materiais e relações.
      </p>
    {/if}
  </aside>
</div>
