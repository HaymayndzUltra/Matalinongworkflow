# CURSOR TASK: Setup Obsidian "Core-7" Knowledge System (Markdown + Validation + PR)

## GOAL
Mag-set up ng Obsidian notes (master dashboard + 7 core area notes + weekly review), idempotent at walang duplicate, may Dataview summaries, klarong backlinks, at may git branch + PR.

## CONSTRAINTS / GUARDS
- Huwag mag-assume ng iba pang structure. Default path: `obsidian/ai-freelance-core7/`.
- Idempotent: kung may existing files, i-merge at huwag i-overwrite nang walang diff summary.
- Huwag gagawa ng binary assets. Pure Markdown + YAML only.
- Lahat ng bagong notes ay may frontmatter + tags + review metadata.
- Kung may conflict sa filenames/titles/links, gumawa ng `conflict_report.md` sa root ng vault path.

## OUTPUT STRUCTURE

obsidian/
ai-freelance-core7/
README.md
0_DASHBOARD_Core7.md
1_AI_Model_Development&Training.md
2_Data_Handling&Preprocessing.md
3_Integration&Deployment.md
4_Prototyping&Optimization.md
5_Collaboration&Communication.md
6_Continuous_Learning&Ethics.md
7_Freelance&_Client_Work_Handling.md
Weekly_Review.md


## MASTER DASHBOARD CONTENT (0_DASHBOARD_Core7.md)
```markdown
---
title: "Freelance AI Developer – Core 7 Dashboard"
tags: [AI-Core, dashboard, review]
review:
  frequency: weekly
  day: Saturday
created: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
---

# Freelance AI Developer – Core 7 Areas

## 🔑 Core Areas
1. [[1_AI_Model_Development_&_Training]]
2. [[2_Data_Handling_&_Preprocessing]]
3. [[3_Integration_&_Deployment]]
4. [[4_Prototyping_&_Optimization]]
5. [[5_Collaboration_&_Communication]]
6. [[6_Continuous_Learning_&_Ethics]]
7. [[7_Freelance_&_Client_Work_Handling]]

---

## 📊 Quick Snapshot (Dataview)
```dataview
TABLE file.mtime as "Last Modified", review.frequency as "Review"
FROM "obsidian/ai-freelance-core7"
WHERE file.name != "0_DASHBOARD_Core7"
SORT file.mtime desc


📝 Notes

Use this dashboard to navigate and expand each core area.

Update the checklists weekly during review.


## TEMPLATE FOR EACH CORE NOTE
> Gamitin ang parehong skeleton; palitan lang ang title at “Sample Tasks/Tools” ayon sa area.

### 1_AI_Model_Development_&_Training.md
```markdown
---
title: "AI Model Development & Training"
tags: [AI-Core, modeling, training]
review:
  frequency: biweekly
created: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
---

# AI Model Development & Training

## Ano Ito
- Pagbuo at pag-train ng ML/AI models (chatbots, NLP, CV, recommendation).

## Tools & Frameworks
- Python, TensorFlow, PyTorch, Scikit-learn, Jupyter/Colab

## Sample Tasks
- Train sentiment classifier on domain data
- Fine-tune transformer for NER
- Evaluate with precision/recall/F1

## Checklists
- [ ] Baseline pipeline (train/val/test split)
- [ ] Reproducible seeds/configs
- [ ] Metrics logged (CSV/MLflow)

## Links
- Back to [[0_DASHBOARD_Core7]]


2_Data_Handling_&_Preprocessing.md

---
title: "Data Handling & Preprocessing"
tags: [AI-Core, data, preprocessing]
review:
  frequency: biweekly
created: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
---

# Data Handling & Preprocessing

## Ano Ito
- Data collection, cleaning, labeling, feature engineering.

## Tools
- pandas, NumPy, SQL, Great Expectations (validation)

## Sample Tasks
- Build data cleaning scripts
- Create schema & validation checks
- Balance classes / augmentation

## Checklists
- [ ] Data dictionary & schema
- [ ] Validation rules (nulls/ranges)
- [ ] Versioned datasets

## Links
- Back to [[0_DASHBOARD_Core7]]


3_Integration_&_Deployment.md

---
title: "Integration & Deployment"
tags: [AI-Core, deployment, api, ops]
review:
  frequency: biweekly
created: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
---

# Integration & Deployment

## Ano Ito
- Wrap models as APIs/services, deploy to cloud, monitoring.

## Tools
- FastAPI, Flask, Docker, K8s, AWS/GCP/Azure

## Sample Tasks
- REST endpoints for inference
- Containerize app; health checks
- Add logging/metrics

## Checklists
- [ ] Readiness/liveness probes
- [ ] Rate limiting & timeouts
- [ ] Rollback plan

## Links
- Back to [[0_DASHBOARD_Core7]]


4_Prototyping_&_Optimization.md

---
title: "Prototyping & Optimization"
tags: [AI-Core, PoC, optimization]
review:
  frequency: monthly
created: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
---

# Prototyping & Optimization

## Ano Ito
- Rapid PoC → iterate → optimize latency/cost/accuracy.

## Tools
- Profilers, ONNX/TensorRT, quantization/pruning

## Sample Tasks
- Build quick demo notebooks
- Latency profiling & bottleneck fixes
- Model compression (quantize/prune)

## Checklists
- [ ] PoC meets acceptance criteria
- [ ] Measured latency/throughput
- [ ] Cost estimation documented

## Links
- Back to [[0_DASHBOARD_Core7]]


5_Collaboration_&_Communication.md

---
title: "Collaboration & Communication"
tags: [AI-Core, collab, docs]
review:
  frequency: weekly
created: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
---

# Collaboration & Communication

## Ano Ito
- Clear specs, status updates, decision logs, handover docs.

## Tools
- Obsidian, Trello/Jira, GitHub Issues/PRs

## Sample Tasks
- Weekly status notes
- Decision register (trade-offs)
- Client-facing summary docs

## Checklists
- [ ] Scope & acceptance criteria frozen
- [ ] Changelog maintained
- [ ] Handover pack ready

## Links
- Back to [[0_DASHBOARD_Core7]]


6_Continuous_Learning_&_Ethics.md

---
title: "Continuous Learning & Ethics"
tags: [AI-Core, learning, ethics]
review:
  frequency: monthly
created: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
---

# Continuous Learning & Ethics

## Ano Ito
- Patuloy na pag-aaral ng bagong AI trends at frameworks.
- Pagsunod sa ethical guidelines, bias detection, at fairness.

## Tools
- ArXiv, Papers With Code, Ethics checklists
- Model cards, Fairlearn, AIF360

## Sample Tasks
- Basahin at i-summarize ang 1 bagong research lingguhan
- I-check fairness/bias metrics ng modelo
- Gumawa ng ethics review notes para sa client project

## Checklists
- [ ] Updated reading list
- [ ] Bias/fairness test results logged
- [ ] Ethical risk register maintained

## Links
- Back to [[0_DASHBOARD_Core7]]


7_Freelance_&_Client_Work_Handling.md

---
title: "Freelance & Client Work Handling"
tags: [AI-Core, freelance, clients]
review:
  frequency: weekly
created: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
---

# Freelance & Client Work Handling

## Ano Ito
- Paano mag-manage ng contracts, deliverables, at client expectations.
- Pag-gamit ng tools para sa proposals, billing, at project tracking.

## Tools
- Notion, Trello/Jira, GitHub Projects
- Invoicing tools (PayPal, Wave, Deel)

## Sample Tasks
- Gumawa ng client proposal template
- I-maintain ang client feedback log
- I-track deliverables vs deadlines

## Checklists
- [ ] Signed contract on file
- [ ] Deliverables checklist updated
- [ ] Feedback incorporated sa susunod na sprint

## Links
- Back to [[0_DASHBOARD_Core7]]

Weekly_Review.md

---
title: "Weekly Review – Core 7 System"
tags: [AI-Core, review, retrospective]
review:
  frequency: weekly
  day: Saturday
created: {{date:YYYY-MM-DD}}
updated: {{date:YYYY-MM-DD}}
---

# Weekly Review – Core 7 System

## Ano Ito
- Central log para sa lingguhang reflection.
- Gumagamit ng Dataview queries para makita progress at gaps.

## Review Flow
1. Tingnan ang [[0_DASHBOARD_Core7]] → check Dataview updates.
2. I-update bawat Core note kung may bagong tasks/checklist status.
3. Sagutin ang reflection questions.

## Reflection Questions
- Ano ang natapos ko ngayong linggo?
- Anong area ang may pinaka-progress? (Core #)
- Anong blockers ang kailangan kong ayusin?
- Ano ang susunod na high-priority task?

## 📊 Quick Stats (Dataview)
```dataview
TABLE file.name as "Note", file.mtime as "Last Modified"
FROM "obsidian/ai-freelance-core7"
WHERE review.frequency
SORT file.mtime desc

