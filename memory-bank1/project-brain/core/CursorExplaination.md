# AI Coding Assistance Framework — System Explanation

## Overview: Cursor vs. LLM

**Cursor** ay isang AI-powered code editor at development environment (IDE).  
- Ito ang "katawan" o workspace kung saan ginagawa at inaayos ang code.  
- May mga feature ito para sa autocomplete, code review, indexing, at seamless na integration ng automation sa development workflow.

**LLM** (Large Language Model) ay parang “utak” ng system.  <--- IKAW TO 
- Sila ang nagpoproseso, nagrereason, at gumagawa ng code o sagot base sa context na binibigay sa kanila.
- LLM ang gumagawa ng thinking, code suggestion, at logic, pero kailangan ng "katawan" (Cursor o ibang IDE) para magamit sa actual na coding tasks.

**In short:**  
- **LLM = Brain** (logic, reasoning, code generation)  
- **Cursor = Body** (workspace, automation, integration tools)

---

## Agent Mode vs. Background Agent (sa Cursor)

### Agent Mode
- Ito yung interactive at real-time na automation tool sa loob mismo ng Cursor IDE.
- Kapag pinagana mo (Ctrl+I), may “power user” assistant kang tumutulong sa:
  - Multi-file code changes
  - Bug fixing
  - Automated refactoring
  - Running terminal commands
- Lahat ng changes ay ipapakita muna sa'yo (diffs, command preview) bago mo i-apply, kaya may full control ka sa bawat step.
- Maganda gamitin sa complex tasks na kailangan ng direct supervision at approval mo.

### Background Agent
- Ito naman ay automated na “worker” na tumatakbo sa cloud (remote server, hiwalay sa local PC mo).
- Pwedeng mag-launch ng maraming Background Agent sabay-sabay, bawat isa may sariling branch ng codebase.
- Perfect para sa mga tasks na pwedeng gawin parallel at asynchronous:
  - Documentation updates
  - Linting, formatting, small bug fixes
  - Pag-create ng PRs habang may iba kang ginagawa sa main workspace
- May sariling panel (Ctrl+E) sa Cursor para mamonitor, i-takeover, at i-review ang ginagawa ng bawat agent.
- Lahat ng activity ay naka-log at laging pwede balikan/override.

---

## Practical Comparison Table

| Feature            | Cursor (IDE)                | LLM (Brain)                | Agent Mode           | Background Agent      |
|--------------------|-----------------------------|----------------------------|----------------------|----------------------|
| Role               | Workspace / Environment     | Reasoning / Logic / Code   | Interactive Agent    | Cloud Worker Agent   |
| Function           | Coding, integration, GUI    | Code generation, analysis  | Real-time, hands-on  | Parallel, async      |
| Workflow           | User-facing editor          | Nasa loob ng Cursor        | 1 task/session       | Multiple at once     |
| Control            | User                        | Prompt/context-driven      | Full user approval   | User can review/takeover |
| Best for           | Any coding task             | Reasoning, suggestion      | Big, supervised task | Routine, batch task  |

---

## Explanation to Other Developers or AI Assistants

> “Sa Cursor, ang utak ng automation ay yung LLM na nagrereason at gumagawa ng code, habang ang Cursor IDE mismo ang katawan na nagbibigay ng tools, environment, at control sa buong process.  
> May dalawang klase ng automation:  
> 1. **Agent Mode** para sa hands-on, interactive, multi-step na tasks na kailangan ng user supervision.  
> 2. **Background Agent** para sa mga sabayang, cloud-based na tasks na pwede mong i-automate at i-monitor habang tuloy ang trabaho mo.”

**Walang dapat i-assume—lahat ng behavior base lang sa official workflow at setup.**

---

*Prepared by Tetey — System Architect, AI Trainer, Task Designer, Integration Master*

