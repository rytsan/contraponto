<script>
  import { onDestroy, onMount, tick } from 'svelte';

  export let dataVisualizations = [];
  export let coveragePairs = [];
  export let articlesRegistry = [];

  let canvasRefs = [];
  let chartInstances = [];
  let selectedOriginArticles = [];
  let selectedChartTitle = '';

  // Constrói conjunto de IDs de artigos existentes no banco/evento
  $: validArticleIds = new Set([
    ...(coveragePairs || []).map((p) => p.article_id),
    ...(articlesRegistry || []).map((a) => a.id)
  ]);

  // Regra de integridade: só renderiza gráficos cujos source_article_ids existam integralmente no banco
  $: verifiedVisualizations = (dataVisualizations || []).filter((viz) => {
    if (!viz || ! Array.isArray(viz.labels) || !Array.isArray(viz.values)) return false;
    if (viz.labels.length === 0 || viz.labels.length !== viz.values.length) return false;
    if (!Array.isArray(viz.source_article_ids) || viz.source_article_ids.length === 0) return false;
    return viz.source_article_ids.every((id) => validArticleIds.has(id));
  });

  function resolveArticlesByIds(ids) {
    const result = [];
    for (const id of ids || []) {
      const fromPair = (coveragePairs || []).find((p) => p.article_id === id);
      const fromReg = (articlesRegistry || []).find((a) => a.id === id);
      if (fromPair || fromReg) {
        result.push({
          id,
          source: fromPair?.source || fromReg?.veiculo || id,
          headline: fromPair?.headline || fromReg?.titulo || '',
          url: fromPair?.url || fromReg?.url_canonica || '',
          position: fromPair?.source_position || fromReg?.posicao_editorial_declarada || ''
        });
      }
    }
    return result;
  }

  function inspectChartSources(viz) {
    selectedChartTitle = viz.title;
    selectedOriginArticles = resolveArticlesByIds(viz.source_article_ids);
  }

  async function renderCharts() {
    chartInstances.forEach((c) => c && c.destroy());
    chartInstances = [];

    if (verifiedVisualizations.length === 0) return;

    const chartModule = await import('chart.js/auto');
    const Chart = chartModule.default || chartModule.Chart;

    verifiedVisualizations.forEach((viz, idx) => {
      const canvas = canvasRefs[idx];
      if (!canvas) return;

      const chartType =
        viz.type === 'timeline' ? 'line' : ['bar', 'line', 'radar'].includes(viz.type) ? viz.type : 'bar';

      const instance = new Chart(canvas, {
        type: chartType,
        data: {
          labels: viz.labels,
          datasets: [
            {
              label: viz.title,
              data: viz.values,
              backgroundColor: ['#9e1b1b', '#e5a93c', '#3b82f6', '#10b981', '#8b5cf6'],
              borderColor: '#f4f1ea',
              borderWidth: 1
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          onClick: () => {
            inspectChartSources(viz);
          },
          plugins: {
            legend: {
              labels: {
                color: '#f4f1ea',
                font: { family: 'monospace', size: 11 }
              }
            }
          },
          scales:
            chartType === 'radar'
              ? {}
              : {
                  x: {
                    ticks: { color: '#d1d5db', font: { size: 11 } },
                    grid: { color: '#2b2b2b' }
                  },
                  y: {
                    ticks: { color: '#d1d5db', font: { size: 11 } },
                    grid: { color: '#2b2b2b' },
                    beginAtZero: true
                  }
                }
        }
      });

      chartInstances.push(instance);
    });

    if (verifiedVisualizations.length > 0 && selectedOriginArticles.length === 0) {
      inspectChartSources(verifiedVisualizations[0]);
    }
  }

  onMount(async () => {
    await tick();
    await renderCharts();
  });

  onDestroy(() => {
    chartInstances.forEach((c) => c && c.destroy());
    chartInstances = [];
  });
</script>

<section aria-labelledby="scene-4-heading" class="space-y-6 py-2">
  <div class="space-y-1 border-b border-[#2b2b2b] pb-4">
    <span class="px-2.5 py-1 rounded font-mono text-xs bg-[#9e1b1b]/25 text-[#f4f1ea] border border-[#9e1b1b]">
      CENA 04 // DADOS E MÉTRICAS VERIFICADAS
    </span>
    <h2 id="scene-4-heading" class="font-serif text-2xl sm:text-3xl font-bold text-[#f4f1ea] pt-1">
      Evidências Quantitativas e Estruturais do Evento
    </h2>
    <p class="text-xs font-mono text-gray-400">
      Clique em qualquer gráfico ou botão de rastreamento para inspecionar as matérias que originaram cada dado.
    </p>
  </div>

  {#if verifiedVisualizations.length === 0}
    <div class="p-12 rounded-lg bg-[#161616] border border-[#2b2b2b] text-center space-y-3">
      <p class="font-serif text-2xl font-bold text-[#e5a93c]">
        Dados insuficientes para visualização honesta.
      </p>
      <p class="font-mono text-xs text-gray-400 max-w-xl mx-auto">
        O Contraponto jamais inventa gráficos no frontend sem métricas reais extraídas e vinculadas a IDs de matérias verificadas no banco de dados.
      </p>
    </div>
  {:else}
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
      <div class="lg:col-span-8 grid grid-cols-1 gap-6">
        {#each verifiedVisualizations as viz, idx (viz.title + idx)}
          <div class="p-5 rounded-lg bg-[#161616] border border-[#2b2b2b] space-y-4">
            <div class="flex flex-wrap items-start justify-between gap-2">
              <div class="space-y-1">
                <span class="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-[#1d1d1d] text-[#e5a93c] border border-[#2b2b2b]">
                  Tipo: {viz.type}
                </span>
                <h3 class="font-serif text-xl font-bold text-[#f4f1ea]">{viz.title}</h3>
                <p class="text-xs text-gray-300">{viz.description}</p>
              </div>
              <button
                type="button"
                on:click={() => inspectChartSources(viz)}
                class="px-3 py-1.5 rounded font-mono text-xs bg-[#1d1d1d] border border-[#e5a93c]/60 text-[#e5a93c] hover:bg-[#9e1b1b] hover:text-[#f4f1ea]"
              >
                Ver artigos de origem ({viz.source_article_ids.length})
              </button>
            </div>

            <div class="h-64 w-full bg-[#0d0d0d] p-3 rounded border border-[#2b2b2b]">
              <canvas bind:this={canvasRefs[idx]} aria-label={viz.title}></canvas>
            </div>

            <!-- Tabela auditável complementar dos valores do gráfico -->
            <div class="overflow-x-auto">
              <table class="w-full text-left border-collapse font-mono text-xs">
                <thead>
                  <tr class="border-b border-[#2b2b2b] text-gray-400">
                    <th class="py-1.5 pr-4">Dimensão / Rótulo</th>
                    <th class="py-1.5">Valor Extraído</th>
                  </tr>
                </thead>
                <tbody>
                  {#each viz.labels as label, i}
                    <tr class="border-b border-[#2b2b2b]/50 text-gray-200">
                      <td class="py-1.5 pr-4">{label}</td>
                      <td class="py-1.5 font-bold text-[#e5a93c]">{viz.values[i]}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </div>
        {/each}
      </div>

      <!-- Painel lateral com artigos que originaram o gráfico clicado -->
      <aside class="lg:col-span-4 bg-[#161616] border border-[#2b2b2b] rounded-lg p-5 space-y-4 sticky top-20">
        <div class="border-b border-[#2b2b2b] pb-3">
          <span class="font-mono text-[10px] uppercase tracking-wider text-[#e5a93c]">
            Rastreabilidade de Dados
          </span>
          <h4 class="font-serif text-lg font-bold text-[#f4f1ea] mt-0.5">
            {selectedChartTitle || 'Artigos de Origem'}
          </h4>
        </div>

        {#if selectedOriginArticles.length > 0}
          <ul class="space-y-3">
            {#each selectedOriginArticles as art}
              <li class="p-3.5 rounded bg-[#121212] border border-[#2b2b2b] space-y-1.5 text-xs">
                <div class="flex items-center justify-between gap-2">
                  <span class="font-mono text-[11px] text-[#e5a93c] font-bold">{art.source}</span>
                  <span class="font-mono text-[10px] text-gray-500">ID: {art.id}</span>
                </div>
                <p class="font-serif text-sm font-semibold text-[#f4f1ea]">{art.headline}</p>
                {#if art.position}
                  <p class="text-[11px] text-gray-400">Posição: {art.position}</p>
                {/if}
                {#if art.url}
                  <a
                    href={art.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="inline-block font-mono text-[11px] text-[#e5a93c] hover:underline pt-1"
                  >
                    Auditar matéria original ↗
                  </a>
                {/if}
              </li>
            {/each}
          </ul>
        {:else}
          <p class="text-xs font-mono text-gray-400">
            Clique em qualquer gráfico ao lado para listar as matérias de origem.
          </p>
        {/if}
      </aside>
    </div>
  {/if}
</section>
