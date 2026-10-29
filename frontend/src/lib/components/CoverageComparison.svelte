<script>
  import EvidenceQuote from './EvidenceQuote.svelte';
  import PoliticalPositionBadge from './PoliticalPositionBadge.svelte';

  export let coveragePairs = [];
  export let isDemo = false;

  // Controle de progressive disclosure (expansão de cada coluna)
  let expandedCards = {};
  // Controle de destaque de vocabulário ideológico por hover (desktop) E clique/toque (mobile)
  let activeTermByCard = {};
  // Por padrão exibe apenas citações verificadas; toggle manual revela não verificadas
  let showUnverifiedQuotes = false;

  function toggleCardExpand(articleId) {
    expandedCards = {
      ...expandedCards,
      [articleId]: !expandedCards[articleId]
    };
  }

  function expandAll(state) {
    const next = {};
    for (const pair of coveragePairs) {
      next[pair.article_id] = state;
    }
    expandedCards = next;
  }

  function handleTermHover(articleId, term) {
    activeTermByCard = {
      ...activeTermByCard,
      [articleId]: term
    };
  }

  function handleTermTapOrClick(articleId, term) {
    const current = activeTermByCard[articleId];
    activeTermByCard = {
      ...activeTermByCard,
      [articleId]: current === term ? null : term
    };
  }

  function formatField(val) {
    if (!val || val === 'sem_evidencia_suficiente') {
      return null;
    }
    return val;
  }

  function highlightIdeologicalTerms(text, terms, activeTerm) {
    if (!text) return [{ text: '', highlighted: false, active: false }];
    const cleanTerms = (terms || []).filter((t) => t && t !== 'sem_evidencia_suficiente');
    if (cleanTerms.length === 0) {
      return [{ text, highlighted: false, active: false }];
    }

    const escaped = cleanTerms
      .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      .sort((a, b) => b.length - a.length);
    const regex = new RegExp(`(${escaped.join('|')})`, 'gi');
    const parts = text.split(regex);

    return parts.filter(Boolean).map((part) => {
      const matchedTerm = cleanTerms.find((t) => t.toLowerCase() === part.toLowerCase());
      const isHighlighted = Boolean(matchedTerm);
      const isActive =
        isHighlighted && activeTerm && matchedTerm.toLowerCase() === activeTerm.toLowerCase();
      return {
        text: part,
        highlighted: isHighlighted,
        active: Boolean(isActive),
        term: matchedTerm || null
      };
    });
  }
</script>

<section aria-labelledby="scene-2-heading" class="space-y-6 py-2">
  <!-- Cabeçalho da Cena 2 e Pergunta Central obrigatória -->
  <div class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <span class="px-2.5 py-1 rounded font-mono text-xs bg-[#9e1b1b]/25 text-[#f4f1ea] border border-[#9e1b1b]">
          CENA 02 // DISPUTA DE ENQUADRAMENTO
        </span>
        <span class="font-mono text-xs text-gray-400">
          {coveragePairs.length} coberturas comparadas lado a lado
        </span>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          on:click={() => expandAll(true)}
          class="px-2.5 py-1 text-xs font-mono rounded border border-[#2b2b2b] bg-[#161616] text-gray-300 hover:border-[#e5a93c]"
        >
          Expandir todas
        </button>
        <button
          type="button"
          on:click={() => expandAll(false)}
          class="px-2.5 py-1 text-xs font-mono rounded border border-[#2b2b2b] bg-[#161616] text-gray-300 hover:border-[#e5a93c]"
        >
          Recolher detalhes
        </button>
        <label
          class="inline-flex items-center gap-2 px-3 py-1 text-xs font-mono rounded border border-[#2b2b2b] bg-[#161616] text-gray-300 cursor-pointer select-none"
        >
          <input
            type="checkbox"
            bind:checked={showUnverifiedQuotes}
            class="accent-[#9e1b1b] rounded"
          />
          <span>Mostrar trechos não verificados</span>
        </label>
      </div>
    </div>

    <div
      class="p-5 rounded-lg bg-gradient-to-r from-[#161616] via-[#9e1b1b]/25 to-[#161616] border border-[#9e1b1b]/70 text-center space-y-1"
    >
      <p class="font-mono text-[11px] uppercase tracking-widest text-[#e5a93c]">
        Eixo Crítico da Comparação
      </p>
      <h2
        id="scene-2-heading"
        class="font-serif text-2xl sm:text-3xl font-bold text-[#f4f1ea]"
      >
        “Quem aparece como sujeito e quem aparece como problema?”
      </h2>
    </div>
  </div>

  <!-- Grade Lado a Lado das Coberturas -->
  <div
    class="grid grid-cols-1 {coveragePairs.length === 2
      ? 'lg:grid-cols-2'
      : 'lg:grid-cols-3'} gap-5 items-start"
  >
    {#each coveragePairs as pair (pair.article_id)}
      {@const isExpanded = Boolean(expandedCards[pair.article_id])}
      {@const activeTerm = activeTermByCard[pair.article_id] || null}
      {@const allQuotes = pair.evidence_quotes || []}
      {@const visibleQuotes = showUnverifiedQuotes
        ? allQuotes
        : allQuotes.filter((q) => q.verified)}
      {@const hiddenUnverifiedCount = allQuotes.filter((q) => !q.verified).length}

      <article
        class="bg-[#161616] border border-[#2b2b2b] rounded-lg overflow-hidden flex flex-col shadow-md"
      >
        <!-- Parte sempre visível: Veículo, Posição Editorial, Manchete e Tese Central -->
        <div class="p-5 space-y-4 border-b border-[#2b2b2b]">
          <div class="space-y-2">
            <div class="flex items-start justify-between gap-2">
              <h3 class="font-mono text-xs uppercase tracking-wider text-[#e5a93c] font-bold">
                {pair.source}
              </h3>
              <a
                href={pair.url}
                target="_blank"
                rel="noopener noreferrer"
                class="text-[11px] font-mono text-gray-400 hover:text-[#e5a93c] shrink-0"
              >
                Abrir fonte ↗
              </a>
            </div>
            <PoliticalPositionBadge position={pair.source_position} {isDemo} />
          </div>

          <h4 class="font-serif text-xl font-bold text-[#f4f1ea] leading-snug">
            {#each highlightIdeologicalTerms(pair.headline, pair.ideological_vocabulary, activeTerm) as seg}
              {#if seg.highlighted}
                <mark
                  class="px-1 rounded {seg.active
                    ? 'bg-[#9e1b1b] text-[#f4f1ea]'
                    : 'bg-[#e5a93c]/25 text-[#e5a93c]'}"
                >
                  {seg.text}
                </mark>
              {:else}
                {seg.text}
              {/if}
            {/each}
          </h4>

          <div class="p-3.5 rounded bg-[#0d0d0d] border border-[#2b2b2b] space-y-1">
            <span class="block font-mono text-[10px] uppercase tracking-wider text-gray-400">
              Tese Central do Enquadramento
            </span>
            <p class="text-sm text-[#f4f1ea]/95 leading-relaxed">
              {#each highlightIdeologicalTerms(pair.central_thesis, pair.ideological_vocabulary, activeTerm) as seg}
                {#if seg.highlighted}
                  <mark
                    class="px-1 rounded {seg.active
                      ? 'bg-[#9e1b1b] text-[#f4f1ea]'
                      : 'bg-[#e5a93c]/25 text-[#e5a93c]'}"
                  >
                    {seg.text}
                  </mark>
                {:else}
                  {seg.text}
                {/if}
              {/each}
            </p>
          </div>

          <!-- Vocabulário Ideológico interativo (hover no desktop + toque/clique no mobile) -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span class="font-mono text-[11px] uppercase tracking-wider text-gray-400">
                Vocabulário Ideológico (passe o mouse ou toque):
              </span>
              {#if activeTerm}
                <button
                  type="button"
                  on:click={() => handleTermTapOrClick(pair.article_id, activeTerm)}
                  class="text-[10px] font-mono text-[#e5a93c] underline"
                >
                  limpar destaque
                </button>
              {/if}
            </div>
            {#if pair.ideological_vocabulary && pair.ideological_vocabulary.length > 0}
              <div class="flex flex-wrap gap-1.5">
                {#each pair.ideological_vocabulary as term}
                  <button
                    type="button"
                    on:mouseenter={() => handleTermHover(pair.article_id, term)}
                    on:mouseleave={() => handleTermHover(pair.article_id, null)}
                    on:click={() => handleTermTapOrClick(pair.article_id, term)}
                    aria-pressed={activeTerm === term}
                    class="px-2.5 py-1 rounded text-xs font-mono border scene-transition {activeTerm ===
                    term
                      ? 'bg-[#9e1b1b] text-[#f4f1ea] border-[#e5a93c]'
                      : 'bg-[#121212] text-[#e5a93c] border-[#e5a93c]/40 hover:border-[#e5a93c]'}"
                  >
                    “{term}”
                  </button>
                {/each}
              </div>
              {#if activeTerm}
                <p class="text-xs font-mono text-[#e5a93c] bg-[#0d0d0d] px-3 py-1.5 rounded border border-[#e5a93c]/40">
                  Termo selecionado: <strong>“{activeTerm}”</strong> — expressão lexical usada para orientar o julgamento do leitor na cobertura de {pair.source}.
                </p>
              {/if}
            {:else}
              <p class="text-xs font-mono text-gray-500 italic">
                Sem evidência suficiente de vocabulário ideológico marcado.
              </p>
            {/if}
          </div>

          <!-- Botão de Progressive Disclosure -->
          <button
            type="button"
            on:click={() => toggleCardExpand(pair.article_id)}
            aria-expanded={isExpanded}
            class="w-full py-2 px-3 rounded bg-[#1d1d1d] hover:bg-[#262626] border border-[#2b2b2b] font-mono text-xs text-[#f4f1ea] flex items-center justify-between"
          >
            <span>
              {isExpanded
                ? 'Ocultar decomposição completa do viés'
                : 'Expandir atores, omissões, enquadramentos e citações'}
            </span>
            <span class="text-[#e5a93c]">{isExpanded ? '▲' : '▼'}</span>
          </button>
        </div>

        <!-- Detalhes colapsáveis (Progressive Disclosure) -->
        {#if isExpanded}
          <div class="p-5 space-y-5 bg-[#121212]">
            <!-- Atores Valorizados vs. Desvalorizados -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div class="p-3 rounded bg-[#161616] border border-emerald-900/50 space-y-1.5">
                <h5 class="font-mono text-[11px] uppercase tracking-wider text-emerald-400">
                  Atores Valorizados (Sujeitos)
                </h5>
                {#if pair.valued_actors && pair.valued_actors.length > 0}
                  <ul class="text-xs text-gray-200 space-y-1 list-disc list-inside">
                    {#each pair.valued_actors as actor}
                      <li>{actor}</li>
                    {/each}
                  </ul>
                {:else}
                  <p class="text-xs text-gray-500 italic">Nenhum ator valorizado identificado.</p>
                {/if}
              </div>

              <div class="p-3 rounded bg-[#161616] border border-[#9e1b1b]/60 space-y-1.5">
                <h5 class="font-mono text-[11px] uppercase tracking-wider text-red-400">
                  Atores Desvalorizados / Problema
                </h5>
                {#if pair.devalued_actors && pair.devalued_actors.length > 0}
                  <ul class="text-xs text-gray-200 space-y-1 list-disc list-inside">
                    {#each pair.devalued_actors as actor}
                      <li>{actor}</li>
                    {/each}
                  </ul>
                {:else}
                  <p class="text-xs text-gray-500 italic">Nenhum ator desvalorizado explícito.</p>
                {/if}
              </div>
            </div>

            <!-- Fontes Privilegiadas e Omissões Prováveis -->
            <div class="space-y-3">
              <div class="p-3 rounded bg-[#161616] border border-[#2b2b2b] space-y-1">
                <h5 class="font-mono text-[11px] uppercase tracking-wider text-[#e5a93c]">
                  Fontes Privilegiadas (Quem tem voz)
                </h5>
                {#if pair.privileged_sources && pair.privileged_sources.length > 0}
                  <ul class="text-xs text-gray-200 space-y-1 list-disc list-inside">
                    {#each pair.privileged_sources as src}
                      <li>{src}</li>
                    {/each}
                  </ul>
                {:else}
                  <p class="text-xs text-gray-500 italic">Sem evidência suficiente.</p>
                {/if}
              </div>

              <div class="p-3 rounded bg-[#161616] border border-[#2b2b2b] space-y-1">
                <h5 class="font-mono text-[11px] uppercase tracking-wider text-amber-400">
                  Omissões Prováveis (O que foi silenciado)
                </h5>
                {#if pair.likely_omissions && pair.likely_omissions.length > 0 && pair.likely_omissions[0] !== 'sem_evidencia_suficiente'}
                  <ul class="text-xs text-gray-200 space-y-1 list-disc list-inside">
                    {#each pair.likely_omissions as om}
                      <li>{om}</li>
                    {/each}
                  </ul>
                {:else}
                  <p class="text-xs text-gray-500 italic">
                    Sem evidência suficiente para apontar omissões específicas.
                  </p>
                {/if}
              </div>
            </div>

            <!-- Quatro Eixos de Enquadramento + Efeito Político -->
            <div class="space-y-2.5 text-xs">
              {#each [
                { label: 'Enquadramento do Estado', value: formatField(pair.state_framing) },
                { label: 'Enquadramento do Mercado', value: formatField(pair.market_framing) },
                { label: 'Enquadramento do Trabalho', value: formatField(pair.labor_framing) },
                { label: 'Enquadramento de Protesto / Luta', value: formatField(pair.protest_framing) },
                { label: 'Efeito Político Provável', value: formatField(pair.political_effect) }
              ] as axis}
                <div class="p-2.5 rounded bg-[#161616] border border-[#2b2b2b]">
                  <span class="block font-mono text-[10px] uppercase text-gray-400 mb-1">
                    {axis.label}
                  </span>
                  {#if axis.value}
                    <p class="text-gray-200 leading-relaxed">{axis.value}</p>
                  {:else}
                    <p class="text-gray-500 italic">
                      Estado vazio honesto: sem evidência suficiente na matéria para este eixo.
                    </p>
                  {/if}
                </div>
              {/each}
            </div>

            <!-- Citações de Evidência (Etapa 3.3) -->
            <div class="space-y-3 pt-2 border-t border-[#2b2b2b]">
              <div class="flex items-center justify-between">
                <h5 class="font-mono text-xs uppercase tracking-wider text-[#e5a93c]">
                  Trechos Textuais Citados ({visibleQuotes.length})
                </h5>
                {#if !showUnverifiedQuotes && hiddenUnverifiedCount > 0}
                  <button
                    type="button"
                    on:click={() => (showUnverifiedQuotes = true)}
                    class="text-[11px] font-mono text-red-300 hover:underline"
                  >
                    +{hiddenUnverifiedCount} não verificado(s) oculto(s)
                  </button>
                {/if}
              </div>

              {#if visibleQuotes.length > 0}
                <div class="space-y-2.5">
                  {#each visibleQuotes as eq}
                    <EvidenceQuote
                      quote={eq.quote}
                      context={eq.context}
                      verified={eq.verified}
                      sourceUrl={pair.url}
                      sourceName={pair.source}
                    />
                  {/each}
                </div>
              {:else}
                <p class="text-xs font-mono text-gray-500 italic">
                  Nenhum trecho verificado disponível para exibição.
                </p>
              {/if}
            </div>
          </div>
        {/if}
      </article>
    {/each}
  </div>
</section>
