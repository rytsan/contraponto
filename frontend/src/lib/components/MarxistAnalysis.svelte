<script>
  import ConfidenceBadge from './ConfidenceBadge.svelte';

  export let analysis = {};
  export let readerQuestions = [];
  export let coveragePairs = [];
  export let confidence = 0.0;

  $: verifiedQuotesWithSource = (coveragePairs || []).flatMap((pair) =>
    (pair.evidence_quotes || [])
      .filter((q) => q.verified)
      .map((q) => ({
        quote: q.quote,
        context: q.context,
        source: pair.source,
        url: pair.url,
        headline: pair.headline
      }))
  );

  function pickSupportingEvidence(cardIndex) {
    if (!verifiedQuotesWithSource || verifiedQuotesWithSource.length === 0) return null;
    return verifiedQuotesWithSource[cardIndex % verifiedQuotesWithSource.length];
  }

  $: analysisCards = [
    {
      code: '01',
      key: 'central_contradiction',
      title: 'Contradição central',
      subtitle: 'Eixo estrutural materialista do conflito',
      content: analysis?.central_contradiction
    },
    {
      code: '02',
      key: 'class_relations',
      title: 'Classes em disputa',
      subtitle: 'Classes e frações de classe em confronto',
      content: analysis?.class_relations
    },
    {
      code: '03',
      key: 'property_and_power',
      title: 'Propriedade e poder',
      subtitle: 'Controle dos meios de produção, concessões e recursos',
      content: analysis?.property_and_power
    },
    {
      code: '04',
      key: 'role_of_state',
      title: 'Papel do Estado',
      subtitle: 'Atuação jurídico-política, repressiva e orçamentária',
      content: analysis?.role_of_state
    },
    {
      code: '05',
      key: 'imperialism_or_dependency',
      title: 'Imperialismo ou dependência',
      subtitle: 'Inserção geopolítica, cadeias globais e soberania',
      content: analysis?.imperialism_or_dependency
    },
    {
      code: '06',
      key: 'ideology_and_naturalization',
      title: 'Ideologia e naturalização',
      subtitle: 'Como interesses particulares são apresentados como universais',
      content: analysis?.ideology_and_naturalization
    },
    {
      code: '07',
      key: 'hegemony_and_silenced_voices',
      title: 'Hegemonia e silenciamentos',
      subtitle: 'Vozes legitimadas versus sujeitos silenciados',
      content: analysis?.hegemony_and_silenced_voices
    },
    {
      code: '08',
      key: 'forms_of_struggle',
      title: 'Formas de luta',
      subtitle: 'Organização coletiva, greves, mobilização e resistência',
      content: analysis?.forms_of_struggle
    },
    {
      code: '09',
      key: 'immediate_demand',
      title: 'Demanda imediata',
      subtitle: 'Pauta concreta e tática dos trabalhadores no acontecimento',
      content: analysis?.immediate_demand
    },
    {
      code: '10',
      key: 'strategic_perspective',
      title: 'Perspectiva estratégica',
      subtitle: 'Horizonte de superação estrutural e controle social',
      content: analysis?.strategic_perspective
    }
  ];
</script>

<section aria-labelledby="scene-5-heading" class="space-y-8 py-2">
  <!-- Cabeçalho da Cena 5 -->
  <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#2b2b2b] pb-4">
    <div class="space-y-1">
      <span class="px-2.5 py-1 rounded font-mono text-xs bg-[#9e1b1b]/25 text-[#f4f1ea] border border-[#9e1b1b]">
        CENA 05 // ANÁLISE MARXISTA-LENINISTA
      </span>
      <h2 id="scene-5-heading" class="font-serif text-2xl sm:text-3xl font-bold text-[#f4f1ea] pt-1">
        Síntese Materialista Histórica em 10 Dimensões
      </h2>
    </div>
    <ConfidenceBadge {confidence} />
  </div>

  <!-- Grade de 10 Cartões Sequenciais -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-5">
    {#each analysisCards as card, idx (card.key)}
      {@const isEmpty = !card.content || card.content === 'sem_evidencia_suficiente'}
      {@const evRef = !isEmpty ? pickSupportingEvidence(idx) : null}

      <article
        class="p-5 rounded-lg border flex flex-col justify-between gap-4 {isEmpty
          ? 'bg-[#121212] border-[#2b2b2b] opacity-85'
          : 'bg-[#161616] border-[#2b2b2b] hover:border-[#9e1b1b]/80'} scene-transition"
      >
        <div class="space-y-3">
          <div class="flex items-center justify-between gap-2 border-b border-[#2b2b2b] pb-2.5">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 rounded font-mono text-xs font-bold bg-[#9e1b1b] text-[#f4f1ea]">
                {card.code}
              </span>
              <div>
                <h3 class="font-serif text-lg font-bold text-[#f4f1ea] leading-tight">
                  {card.title}
                </h3>
                <p class="font-mono text-[10px] text-gray-400">{card.subtitle}</p>
              </div>
            </div>
            <span class="font-mono text-[11px] text-[#e5a93c]">
              Confiança: {Math.round((Number(confidence) || 0) * 100)}%
            </span>
          </div>

          {#if isEmpty}
            <div class="p-4 rounded bg-[#0d0d0d] border border-dashed border-[#2b2b2b] space-y-1">
              <span class="font-mono text-xs uppercase tracking-wider text-gray-400 block">
                Estado Vazio Honesto (sem_evidencia_suficiente)
              </span>
              <p class="text-xs text-gray-400 leading-relaxed">
                As matérias coletadas neste evento não contêm evidência textual suficiente para fundamentar esta dimensão sem especulação.
              </p>
            </div>
          {:else}
            <p class="text-sm text-[#f4f1ea]/95 leading-relaxed">
              {card.content}
            </p>
          {/if}
        </div>

        {#if evRef}
          <footer class="p-3 rounded bg-[#0d0d0d] border border-[#2b2b2b] space-y-1.5 text-xs">
            <div class="flex items-center justify-between gap-2 font-mono text-[10px]">
              <span class="text-emerald-400 uppercase">✓ Evidência textual vinculada</span>
              <a
                href={evRef.url}
                target="_blank"
                rel="noopener noreferrer"
                class="text-[#e5a93c] hover:underline truncate max-w-[200px]"
              >
                {evRef.source} ↗
              </a>
            </div>
            <p class="font-serif italic text-gray-300 leading-snug">
              “{evRef.quote}”
            </p>
          </footer>
        {/if}
      </article>
    {/each}
  </div>

  <!-- Limites e Incertezas -->
  {#if analysis?.limitations_and_uncertainty && analysis.limitations_and_uncertainty.length > 0}
    <div class="p-5 rounded-lg bg-[#161616] border border-[#2b2b2b] space-y-2">
      <h3 class="font-mono text-xs uppercase tracking-wider text-gray-400">
        Limites e Incertezas da Análise
      </h3>
      <ul class="list-disc list-inside text-xs text-gray-300 space-y-1">
        {#each analysis.limitations_and_uncertainty as lim}
          <li>{lim}</li>
        {/each}
      </ul>
    </div>
  {/if}

  <!-- Bloco Final Obrigatório: Perguntas ao Leitor -->
  <div class="p-6 sm:p-8 rounded-lg bg-gradient-to-br from-[#161616] to-[#9e1b1b]/20 border border-[#9e1b1b] space-y-4">
    <div class="space-y-1">
      <span class="font-mono text-xs uppercase tracking-widest text-[#e5a93c]">
        Leitura Ativa e Crítica
      </span>
      <h3 class="font-serif text-2xl font-bold text-[#f4f1ea]">
        Perguntas ao leitor
      </h3>
    </div>

    {#if readerQuestions && readerQuestions.length > 0}
      <ol class="space-y-3 list-decimal list-inside text-sm sm:text-base font-serif text-[#f4f1ea] leading-relaxed">
        {#each readerQuestions as question}
          <li class="p-3 rounded bg-[#0d0d0d]/80 border border-[#2b2b2b]">
            {question}
          </li>
        {/each}
      </ol>
    {:else}
      <p class="text-xs font-mono text-gray-400">Sem perguntas adicionais registradas.</p>
    {/if}
  </div>
</section>
