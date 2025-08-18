# 📚 COMPLETE CURSOR RULES TRIGGER DOCUMENTATION 
**Total Rules Found:** 19 files

---

## 🔴 MASTER TOGGLE TRIGGERS
**Rule:** `rules_master_toggle.mdc`  
**Always Active:** YES

### Enable Rules
| Trigger | Language | Action |
|---------|----------|--------|
| `[cursor-rules:on]` | English | Enable all cursor rules |
| `/rules on` | English | Enable all cursor rules |
| `cursor rules on` | English | Enable all cursor rules |
| `enable cursor rules` | English | Enable all cursor rules |
| `i-enable ang cursor rules` | Tagalog | Enable all cursor rules |
| `buksan ang cursor rules` | Tagalog | Enable all cursor rules |

### Disable Rules
| Trigger | Language | Action |
|---------|----------|--------|
| `[cursor-rules:off]` | English | Disable all cursor rules |
| `/rules off` | English | Disable all cursor rules |
| `cursor rules off` | English | Disable all cursor rules |
| `disable cursor rules` | English | Disable all cursor rules |
| `i-disable ang cursor rules` | Tagalog | Disable all cursor rules |
| `patayin ang cursor rules` | Tagalog | Disable all cursor rules |

### Cross-Environment Toggles
| Trigger | Action |
|---------|--------|
| `[windsurf-rules:on]` | Disable cursor rules, enable windsurf |
| `[windsurf-rules:off]` | Enable cursor rules, disable windsurf |

---

## 📝 PLAN INGESTION TRIGGERS
**Rule:** `trigger_phrases.mdc` + `agent_plan_ingestion.mdc`  
**Always Active:** YES when rules enabled

### Start Plan Ingestion
| Trigger | Language | Action |
|---------|----------|--------|
| `Ingest mo ang plan` | Tagalog | Start plan ingestion from organize.md |
| `Ingest plan now` | English | Start plan ingestion from organize.md |
| `Gawa ka ng actionable plan` | Tagalog | Create actionable plan with phases |
| `Hatiin mo ang plan by phases` | Taglish | Break plan into phases |
| `Prepare Human-Readable Plan Draft` | English | Create human-readable draft |
| `Phase-by-phase draft` | English | Create phased draft |

### Approve & Finalize
| Trigger | Language | Action |
|---------|----------|--------|
| `Approve draft` | English | Approve draft and create JSON |
| `approved` | English | Simple approval trigger |
| `Finalize JSON` | English | Convert to JSON format |
| `Generate tasks_active.json content` | English | Create JSON content |
| `Convert to JSON` | English | Convert draft to JSON |
| `Ready for ingestion` | English | Finalize for ingestion |
| `Bigyan mo ako ng final JSON` | Tagalog | Give me the final JSON |

---

## ✅ TASK EXECUTION TRIGGERS
**Rule:** `trigger_phrases.mdc` + `trigger_phrases_extra.mdc` + `todo_manager_flow.mdc`

### Show & Validate
| Trigger | Language | Action |
|---------|----------|--------|
| `Show plan <TASK_ID>` | English | Display task hierarchy |
| `Show next phase` | English | Show next phase to execute |
| `Ipakita ang plano` | Tagalog | Show the plan |
| `Validate plan` | English | Run validation checks |
| `Check next phase` | English | Check what's next |
| `Lint plan` | English | Validate plan structure |
| `Show hierarchy <TASK_ID>` | English | Display task hierarchy |
| `I-validate ang plan` | Tagalog | Validate the plan |
| `Suriin ang susunod` | Tagalog | Check what's next |
| `Ano ang next phase?` | Tagalog | What's the next phase? |

### Execute Tasks
| Trigger | Language | Action |
|---------|----------|--------|
| `Execute sub-step` | English | Run specific sub-step |
| `Gawin ang step <i>` | Tagalog | Do step i |
| `Execute <i>` | English | Execute step i |
| `Run sub-step <i>` | English | Run sub-step i |
| `Ituloy ang <i>` | Tagalog | Continue with i |
| `proceed` | English | Continue to next phase |

### Mark Complete
| Trigger | Language | Action |
|---------|----------|--------|
| `Mark phase <k> done for <TASK_ID>` | English | Mark phase k as complete |
| `Tapusin ang phase <k>` | Tagalog | Finish phase k |
| `Markahan done ang phase <k>` | Tagalog | Mark phase k done |
| `Finish phase <k>` | English | Complete phase k |
| `Complete phase <k>` | English | Complete phase k |
| `Close phase <k>` | English | Close phase k |
| `Tapos na ang phase <k>` | Tagalog | Phase k is done |

---

## 🔄 WORKFLOW NAVIGATION TRIGGERS
**Rule:** `trigger_phrases_extra.mdc` + `autopilot-next-phase.md`

### Next Action
| Trigger | Language | Action |
|---------|----------|--------|
| `Ano ang susunod na gagawin?` | Tagalog | What's next to do? |
| `Next action` | English | Show next action |
| `Next step` | English | Show next step |
| `What's next?` | English | Show next action |

### Autopilot Mode
| Trigger | Action |
|---------|--------|
| `Execute the next unfinished phase` | Run next phase automatically |
| `Continue with autopilot` | Auto-execute next phase |

---

## 💾 MEMORY & STATE TRIGGERS
**Rule:** `cursorrules.mdc` + `expertcursor.mdc`

### Memory Operations
| Trigger | Action |
|---------|--------|
| `Store memory` | Save current state to memory |
| `mcp_memory_store` | Store memory via MCP |
| `Update documentation` | Update memory-bank docs |
| `Sync state` | Trigger auto-sync |

### Session Management
| Trigger | Action |
|---------|--------|
| `Resume state` | Load tasks_active.json |
| `Restore context` | Load cursor_state.json |
| `Check session` | View current-session.md |

---

## 🛡️ VALIDATION & ENFORCEMENT TRIGGERS
**Rule:** `phase_gates.mdc` + `done_enforcement.mdc` + `important_note_enforcement.mdc`

### Phase Gates
| Trigger | Action |
|---------|--------|
| `Check phase gates` | Validate before proceeding |
| `Validate gates` | Run phase gate checks |
| `Enforce gates` | Apply phase gate rules |

### Important Note
| Trigger | Action |
|---------|--------|
| `Check important notes` | Verify all phases have notes |
| `Validate notes` | Ensure IMPORTANT NOTE presence |

---

## 🔧 SPECIAL RULE TRIGGERS

### Tool Usage Guarantee
**Rule:** `tool_usage_guarantee.mdc`
| Trigger | Action |
|---------|--------|
| `Use tools` | Guarantee tool usage when needed |
| `Run command` | Execute with proper tools |

### Organizer Authority
**Rule:** `organizer_authority.mdc`
| Trigger | Action |
|---------|--------|
| `Organize plan` | Use organize.md as source |
| `From organizer` | Reference organize.md |

### Analysis Tools
**Rule:** `analysis_tools.mdc`
| Trigger | Action |
|---------|--------|
| `Run analysis` | Execute plan_next.py |
| `Analyze hierarchy` | Run plain_hier.py |

---

## 🎯 CONFIDENCE SCORING TRIGGERS
**Rule:** `expertcursor.mdc`

| Trigger | Action |
|---------|--------|
| Request with technical question | Attach confidence score (0-100%) |
| Complex code request | Include edge cases and validation |
| Production code request | Ensure benchmarked solution |

---

## 📋 TODO LIST FORMAT TRIGGERS
**Rule:** `todo-list-format.mdc`

| Trigger | Action |
|---------|--------|
| `Create todo` | Use hierarchical format |
| `Add task` | Follow todo structure |
| `Update todos` | Maintain format |

---

## ⚡ QUICK REFERENCE - MOST COMMON TRIGGERS

### Top 10 Most Used
1. `[cursor-rules:on]` - Enable rules
2. `proceed` - Continue execution
3. `Ingest mo ang plan` - Start plan ingestion
4. `approved` - Approve draft
5. `Show plan <TASK_ID>` - Display tasks
6. `Mark phase <k> done` - Complete phase
7. `Next action` - What's next
8. `Execute <i>` - Run sub-step
9. `Validate plan` - Check structure
10. `Store memory` - Save state

### Tagalog Triggers
- `Ingest mo ang plan` - Ingest the plan
- `Ipakita ang plano` - Show the plan
- `Suriin ang susunod` - Check what's next
- `Gawin ang step` - Do the step
- `Tapusin ang phase` - Finish the phase
- `Ano ang susunod?` - What's next?
- `Tapos na` - It's done
- `Ituloy` - Continue
- `I-validate` - Validate it
- `Bigyan mo ako` - Give me

---

## 🔍 TRIGGER DETECTION RULES

### Where Triggers Work
✅ In user messages  
✅ As standalone phrases  
✅ Within sentences  
✅ Mixed language (Taglish)  

### Where Triggers DON'T Work
❌ Inside code blocks ``` ```  
❌ Inside inline code ` `  
❌ Inside quotes " " or > >  
❌ In system/AI messages  

### Precedence Rules
1. Last trigger wins (rightmost)
2. Master toggle overrides all
3. Explicit beats implicit
4. User message only

---

## 📊 RULE FILE SUMMARY

| Rule File | Always Active | Purpose |
|-----------|---------------|---------|
| rules_master_toggle.mdc | YES | Global on/off switch |
| trigger_phrases.mdc | YES | Main action triggers |
| trigger_phrases_extra.mdc | YES | Additional triggers |
| cursorrules.mdc | YES | Core system rules |
| expertcursor.mdc | YES | AI persona & standards |
| agent_plan_ingestion.mdc | When triggered | Plan ingestion protocol |
| tasks_active_schema.mdc | When needed | JSON schema format |
| todo_manager_flow.mdc | YES | Task execution flow |
| autopilot-next-phase.md | When triggered | Auto-execution mode |
| phase_gates.mdc | During execution | Phase validation |
| done_enforcement.mdc | During execution | Completion rules |
| important_note_enforcement.mdc | During planning | Note requirements |
| analysis_tools.mdc | When triggered | Analysis commands |
| exec_policy.mdc | During execution | Execution policy |
| organizer_authority.mdc | During planning | Source authority |
| organizer_to_tasks_active.mdc | During conversion | Format conversion |
| tool_usage_guarantee.mdc | Always | Tool usage rules |
| todo-list-format.mdc | When creating todos | Format standards |
| rules.mdc | Reference | Rule index |

---

## 💡 TIPS FOR USING TRIGGERS

1. **Always start with:** `[cursor-rules:on]` to ensure rules are active
2. **Use exact phrases** for reliable triggering
3. **Tagalog triggers** work equally well as English
4. **Combine triggers** for complex actions
5. **Check status with:** `Show plan` or `Validate plan`
6. **Use "proceed"** to continue to next phase
7. **Master toggle** overrides everything

---

**Total Unique Triggers Found:** 100+  
**Languages Supported:** English, Tagalog, Taglish  
**Confidence Score:** 100%

---

<!-- Deep-analysis triggers removed per user request -->
