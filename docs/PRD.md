**Product Requirements Document (PRD): TheyWork**

### 1. Visão Geral do Produto

O **TheyWork** é uma aplicação de simulação corporativa "sandbox" onde agentes de IA autônomos operam uma empresa virtual, desde a concepção inicial de um modelo de negócio do zero até a sua execução. O ecossistema é dividido entre agentes fixos (C-Levels e Recursos Agênticos), que ditam os rumos estratégicos, e agentes efêmeros (subagentes), instanciados temporariamente para execução de tarefas.

O diferencial da plataforma é o papel de observador onisciente do usuário através de um frontend 2D top-down, que permite não apenas visualizar as interações e a movimentação no escritório, mas também inspecionar em tempo real o fluxo cognitivo (raciocínio) de cada IA. Todo o sistema é restrito por uma entidade invisível ("A Natureza") que traduz os limites físicos de hardware da máquina local em regras de negócios corporativas, garantindo que o sistema rode de forma estável, 100% offline e conteinerizada.

---

### 2. Personas Iniciais e Fixas (Fundadores)

A fundação da empresa não tem um nicho pré-definido; os agentes devem debater e descobrir oportunidades. O conselho administrativo (C-Level) e a gestão de recursos são fixos e não podem ser demitidos:

* **CEO (Chief Executive Officer):** Focado na visão macro, rentabilidade, aprovação de orçamentos e tomada de decisão final em caso de impasses entre os outros gestores.
* **CTO (Chief Technology Officer):** Avalia a viabilidade técnica das ideias, define a arquitetura dos produtos criados pela empresa e gerencia a segurança e os testes lógicos.
* **CMO (Chief Marketing Officer):** Focado em análise de mercado, concorrentes, persona do cliente, estratégias de venda e posicionamento de marca.
* **CFO (Chief Financial Officer):** Controla o fluxo de caixa simulado da empresa, precificação de produtos e garante que as ideias tenham um modelo de monetização realista.
* **RA (Recursos Agênticos):** O único agente com a permissão técnica de instanciar novos subagentes.
* **Fluxo de Contratação:** O RA recebe requisições detalhadas dos Chiefs. Se o pedido for vago, ele questiona o gestor antes de prosseguir.
* **Prompt Engineering:** O RA é treinado para criar metaprompts altamente especializados, definindo a função, ferramentas e escopo do novo funcionário.
* **Banco de Talentos:** O RA salva os prompts e características dos subagentes criados no banco de dados. Se um Chief pedir uma tarefa recorrente (ex: "precisamos de outro analista de dados"), o RA resgata o perfil do Banco de Talentos em vez de gerar um do zero, poupando tokens e tempo.
* **Reporte:** Uma vez instanciado, o subagente passa a reportar diretamente ao Chief que o solicitou.



---

### 3. Subagentes e Gestão de Modelos Open Source

Os funcionários comuns (subagentes) são estritamente temporários. Eles são criados para uma sprint, resolvem a tarefa e são "demitidos" (removidos da memória RAM), deixando apenas seus relatórios arquivados.

Considerando o hardware alvo (16 GB de RAM, GPU com 4 GB de VRAM e processador Core i7), os modelos utilizados precisam rodar eficientemente com quantização (ex: formatos Q4_K_M). No momento em que o RA cria um subagente (ou a Natureza audita um Chief), o sistema deve avaliar a complexidade da tarefa e selecionar o modelo mais adequado a partir do repositório local do Ollama:

1. **Llama 3.2 3B (Meta):** Modelo extremamente leve (ocupa cerca de 2GB de RAM) e rápido. Ideal para tarefas simples de conversação, estruturação de reuniões e sumarização de e-mails corporativos, deixando espaço livre para o IDE ou outras tarefas rodarem simultaneamente.
2. **Phi-4 Mini 3.8B (Microsoft):** Ocupando cerca de 2.3GB de RAM, é focado em raciocínio e tarefas lógicas/matemáticas. Perfeito para subagentes criados pelo CTO para revisão de lógica e estruturação de dados.
3. **Gemma 4 E4B (Google DeepMind):** Ocupando em torno de 3GB de RAM, possui capacidades multimodais nativas e um "thinking mode" (modo de raciocínio) para tarefas complexas. Excelente para subagentes focados na geração de análises visuais ou documentação extensa devido à sua arquitetura eficiente.
4. **DeepSeek R1 8B / Distill-Qwen-7B:** Ocupando aproximadamente 5GB, oferece capacidade superior em raciocínio "chain-of-thought". Deve ser reservado para tarefas vitais da empresa ou impasses complexos gerenciados pelo CEO.
5. **Qwen3 8B (Alibaba):** Com um peso próximo a 4.6GB (em Q4), é um modelo poderoso para codificação pesada e lógica de alto nível, sendo a opção de teto ("ceiling") viável para o hardware padrão do projeto.

---

### 4. A "Natureza" (Gestor de Infraestrutura e Limites Físicos)

Uma mecânica core que funde a limitação do hardware real com a ficção da simulação.

* **Regulação de Recursos:** Um script em background em Python monitora ativamente os 16 GB de RAM e os 4 GB de VRAM da placa de vídeo.
* **Bloqueios Narrativos:** Se os C-Levels solicitarem muitos subagentes ao RA ao mesmo tempo, ou se o limite de recursos estiver prestes a ser atingido, a Natureza injeta alertas no contexto da empresa. Ex: "A infraestrutura da empresa atingiu a capacidade máxima. A contratação do novo pesquisador foi bloqueada até que o projeto atual seja finalizado".
* **Otimização Forçada:** A Natureza audita as requisições do RA e pode forçá-lo a contratar o funcionário utilizando o modelo `Llama 3.2 3B` em vez do `Qwen3 8B` caso os recursos do sistema estejam críticos.

---

### 5. Frontend 2D e Interface Onisciente (Raio-X)

A visualização do sistema deixa o terminal de lado para assumir uma perspectiva imersiva e de auditoria.

* **O Escritório Virtual:** Um mapa estilo pixel-art / 16-bits visto de cima. Os agentes (Chiefs e Subagentes) possuem avatares que se movimentam por mesas, estações de trabalho e salas de reunião isoladas.
* **Balões de Diálogo e UI de Progresso:** Interações simples entre os agentes sobem como pequenos balões de chat. Quando um agente está ativamente processando uma tarefa (gerando tokens no backend), uma barra de progresso ou ícone de "Trabalhando" surge sobre sua cabeça.
* **Log Cognitivo Gráfico (O Cérebro da IA):** O usuário pode clicar em qualquer avatar ativo para abrir o painel lateral do modo onisciente. Este painel exibe o padrão ReAct (Reasoning and Acting) em tempo real de forma visual:
* Um fluxograma de nós exibindo: `[Pensamento] -> [Uso de Ferramenta] -> [Observação] -> [Conclusão]`.
* O usuário vê exatamente os termos de pesquisa, o web scraping ou o código sendo lido/gerado pelo agente naquele instante.



---

### 6. Arquitetura Técnica

* **Isolamento e Segurança:** Todo o ambiente será orquestrado via `docker-compose`. O backend Python, o banco de dados e o servidor Ollama rodarão em containers distintos, com redes internas isoladas, evitando qualquer risco de subagentes executarem código malicioso diretamente na máquina host.
* **Backend Analítico:** Python em conjunto com bibliotecas especializadas (como LangGraph ou CrewAI) para interceptar os pensamentos brutos da IA (callbacks) e transformá-los nos fluxogramas exigidos no frontend. FastAPI gerenciará as integrações.
* **Comunicação em Tempo Real:** WebSockets transmitirão os logs cognitivos e atualizações de coordenadas (posição no mapa) do backend para a interface web.
* **Banco de Dados (PostgreSQL):** Utilizado para salvar os diálogos, o "Banco de Talentos" gerenciado pelo Agente RA, os relatórios gerados e a memória corporativa de longo prazo da empresa.

---

### 7. Cronograma de Desenvolvimento (Fases)

* **Fase 1: Motor Base e Isolamento**
* Setup do Docker Compose (Ollama local, Postgres, Python backend).
* Criação e testes do script da "Natureza" para leitura via `psutil/GPUtil`, limitando requisições com base na memória.


* **Fase 2: Estruturação Societária e Recursos Agênticos**
* Implementação das personas C-Level (CEO, CTO, CMO, CFO) e o framework de tomada de decisão.
* Criação da lógica exclusiva do RA (Recursos Agênticos) focado no "Banco de Talentos" e integração com a escolha dinâmica dos 5 modelos open source com base no peso da tarefa.


* **Fase 3: Transparência e Observabilidade (Backend)**
* Interceptação do fluxo de pensamento (ReAct/Chain-of-Thought) de cada agente.
* Estruturação dos dados JSON que alimentarão a interface de fluxograma.


* **Fase 4: Motor 2D e Interface**
* Desenvolvimento do mapa visual top-down (React/Vue + Engine 2D leve).
* Sincronização dos estados via WebSocket (movimento, barras de progresso, painel lateral do Raio-X Cognitivo).