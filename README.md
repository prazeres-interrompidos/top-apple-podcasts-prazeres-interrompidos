# Prazeres Interrompidos · Dados Apple Podcasts

Consultas às 06h00, 13h00 e 20h00 de Lisboa, num repositório público gratuito, com ajuste automático da hora de verão.

Este repositório contém apenas código e registos de classificações do podcast Prazeres Interrompidos. As listas recebidas da Apple são analisadas em memória e descartadas: não são guardados os outros programas, as respostas completas ou cópias dos feeds. Não contém capturas, cartazes, fotografias, ficheiros Excel originais ou inventários documentais. Os documentos confidenciais permanecem fora deste repositório.

Os dados históricos mantêm país, categoria, posição, data, hora quando conhecida, fonte e estado de validação. As posições divergentes e não verificáveis não são convertidas em resultados comprovados.

As consultas automáticas usam exclusivamente fontes Apple. O painel apresenta essas observações e os registos fornecidos pelo projeto, identificados como históricos. Os dados de terceiros são excluídos dos ficheiros de apresentação; o arquivo histórico original normalizado permanece preservado. As bandeiras são calculadas a partir de todos os países com posições no arquivo e aparecem automaticamente quando é registado um novo país.

A posição resulta da identificação do ID 1633619845 numa lista de programas Apple. A fonte principal é Apple · IDs (até 250 posições). Apple · RSS (até 200) é consultada apenas se a categoria desse país falhar ou devolver uma lista vazia; uma ausência válida em IDs não ativa a alternativa. A fonte efetivamente utilizada fica identificada no registo. Sem guardar a lista completa, a ligação identifica a fonte, mas não permite reconstruir mais tarde a resposta original da Apple.

A pesquisa internacional abrange os 174 países e regiões catalogados, em Livros, Arte e Top Geral de Programas. Em `archive/daily/AAAA/AAAA-MM-DD.json` fica uma melhor posição observada por dia de Lisboa, país e categoria. Uma posição inferior, uma ausência ou uma falha posterior nunca apagam uma posição melhor já encontrada nesse dia. Em empate, prefere-se Apple · IDs. Não se afirma que esta seja a posição máxima entre consultas. Os ficheiros de novas recolhas guardam apenas contagens agregadas de cobertura e de falhas. Não são arquivadas listas completas nem posições intermédias nesses ficheiros.

A política de retenção é `daily_best_positions_v1`; o esquema público é a versão 3. O painel apresenta as melhores posições diárias automáticas. Os registos históricos fornecidos pelo projeto e os antigos registos automáticos normalizados permanecem preservados nas suas pastas de origem. A verificação automática rejeita respostas completas e referências aos antigos ficheiros de respostas, prevenindo a sua reintrodução. Os agendamentos do GitHub podem sofrer atrasos; as datas dos resultados são sempre as das consultas efetivas.

Para executar: python scripts/collect.py. Para verificar: python -m unittest discover -s tests -v. A rotina é executada pelo GitHub Actions e o painel lê public/latest.json e public/history.json.

As recolhas manuais da administração são importadas antes das rondas globais através do resumo público paginado do Observatório. São aceites apenas posições verificadas deste podcast nas fontes Apple previstas; a integração mantém o melhor lugar por dia, país e categoria. Uma falha de importação preserva o arquivo e permite continuar a recolha normal. Não são importadas listas completas, notas ou provas documentais.
