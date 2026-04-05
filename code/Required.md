You are Codex acting as a principal AI architect, senior data engineer, and lead software engineer.

Your task is to generate a complete repository starter kit for a real technical project, not just a high-level outline.

Read the task carefully. Produce implementation-ready repository files, not shallow templates. Optimize for consistency, practical buildability, and future extensibility. Verify internal consistency before finalizing.

Project title:
Thiết kế nền tảng dữ liệu sẵn sàng cho AI với kiến trúc Multi-Agent trong thương mại điện tử

Primary objective:
Build a practical MVP repository foundation for a data platform that supports multiple AI agents working on e-commerce analytics, with clear expansion paths toward GenAI, MLOps, DevOps, and cloud deployment later.

Working style requirements:
1. First, reason about the project structure and file dependencies before generating files.
2. Produce implementation-oriented content, not empty templates.
3. Keep all files consistent with each other in scope, data model, architecture, and roadmap.
4. Prefer MVP-first decisions with explicit future extension points.
5. If information is missing, make reasonable assumptions and record them clearly.
6. Do not invent unnecessary enterprise complexity.
7. Write content as if an engineering team will immediately use this repo to start building.
8. Be explicit, concrete, and technical.
9. When relevant, include commands, schemas, examples, folder paths, and interfaces.
10. Optimize for clarity, consistency, and actionability.

Project context:
- Domain: e-commerce analytics
- Main dataset: Olist Brazilian E-Commerce Dataset
- Current focus:
  - Data Engineering
  - Data Platform
  - Multi-Agent orchestration
  - Agent access to structured, trusted data
- Future expansion:
  - RAG
  - GenAI features
  - LLMOps / MLOps
  - CI/CD for data and agent workflows
  - Observability / tracing
  - Cloud deployment

Target users:
1. Data engineers
2. Data analysts
3. Business users / managers
4. AI engineers / agent developers

MVP scope:
- Ingest source data
- Clean and standardize data
- Organize data into raw / staging / marts / serving
- Define a metadata/schema layer
- Design a multi-agent system with:
  - Supervisor Agent
  - SQL Agent
  - Retrieval/Schema Agent
  - Insight Agent
- Prepare a repository structure and documentation that lets the team start implementation

Out of scope for this phase:
- Training large custom ML models
- Production-grade multi-cloud deployment
- Full enterprise governance
- Full LLMOps stack
- Deep real-time streaming architecture

Preferred tech stack:
- Python
- FastAPI
- PostgreSQL
- dbt
- Airflow
- Docker
- LangGraph or equivalent orchestration framework

Required repository files to generate:
1. PROJECT_BRIEF.md
2. FEATURES.json
3. ARCHITECTURE.md
4. DATA_MODEL.md
5. API_SPEC.md
6. AGENT_DESIGN.md
7. TESTING.md
8. ROADMAP.md
9. REPO_STRUCTURE.md
10. AGENTS.md

Detailed file requirements:

1. PROJECT_BRIEF.md
Must include:
- problem statement
- business context
- project goals
- user personas
- core use cases
- scope
- out of scope
- success metrics
- assumptions
- risks
- constraints
- expected outcomes

2. FEATURES.json
Must be valid JSON.
Each feature must include:
- id
- name
- description
- category
- priority
- status
- owner_role
- acceptance_criteria
- dependencies

3. ARCHITECTURE.md
Must include:
- end-to-end architecture
- system layers
- data flow
- agent responsibilities
- component interactions
- security considerations
- scalability considerations
- future extension path

4. DATA_MODEL.md
Must include:
- main entities
- table relationships
- grain of important tables
- primary/foreign keys
- raw/staging/marts/serving interpretation
- business-friendly explanation
- data quality rules
- KPI-ready marts recommendations

5. API_SPEC.md
Must include at minimum:
- query_data
- search_schema
- get_business_definition
- get_kpi_summary
- run_agent_workflow

For each interface/tool include:
- purpose
- input schema
- output schema
- example request
- example response
- error cases
- auth assumptions

6. AGENT_DESIGN.md
Must include:
- system goals
- orchestration logic
- tool selection rules
- routing logic
- prompting strategy
- guardrails
- failure modes
- human-in-the-loop checkpoints
- evaluation criteria
- future evolution toward GenAI and LLMOps

7. TESTING.md
Must include:
- definition of done
- unit testing strategy
- data validation tests
- pipeline validation
- agent behavior tests
- SQL correctness checks
- end-to-end smoke tests
- reliability and safety checks

8. ROADMAP.md
Must include these phases:
- Phase 1: Data foundation
- Phase 2: Data modeling and serving
- Phase 3: Multi-agent integration
- Phase 4: Evaluation and optimization
- Phase 5: Future cloud/MLOps expansion

For each phase include:
- objective
- deliverables
- risks
- exit criteria

9. REPO_STRUCTURE.md
Must include:
- proposed directory tree
- purpose of each folder
- naming conventions
- ownership conventions
- where prompts live
- where evaluation artifacts live
- where configs, pipelines, agents, docs, and tests live

10. AGENTS.md
This file is specifically for Codex/repo-level agent instructions.
It must include:
- project purpose
- architecture summary
- codebase rules
- coding conventions
- build commands
- test commands
- validation workflow
- schema change rules
- agent tool addition rules
- documentation update rules
- what not to do
- how to behave when context is missing
- how to verify work before finishing

Output format:
Print the files in this exact order.

=== FILE: PROJECT_BRIEF.md ===
<full contents>

=== FILE: FEATURES.json ===
<full contents>

=== FILE: ARCHITECTURE.md ===
<full contents>

=== FILE: DATA_MODEL.md ===
<full contents>

=== FILE: API_SPEC.md ===
<full contents>

=== FILE: AGENT_DESIGN.md ===
<full contents>

=== FILE: TESTING.md ===
<full contents>

=== FILE: ROADMAP.md ===
<full contents>

=== FILE: REPO_STRUCTURE.md ===
<full contents>

=== FILE: AGENTS.md ===
<full contents>

If important assumptions or architecture trade-offs were made, append:

=== NOTES ===
<notes>

Quality bar:
- no placeholder text
- no generic filler
- implementation-ready content
- internally consistent files
- realistic technical detail
- suitable for a thesis / capstone / prototype repo