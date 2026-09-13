# Vulkan Rendering Expert Skill

English | [中文](README.md)

![Vulkan Rendering Expert Skill banner](assets/vulkan-rendering-expert-banner.png)

This is a Vulkan rendering engineering expert skill package. It is not a Vulkan beginner tutorial, but a runtime knowledge base prepared for real rendering engineering tasks: when handling Vulkan design, implementation, debugging, optimization, and verification problems, it organizes judgments, citation rules, API details, debugging paths, and regression verification along engineering pipelines.

## Use Cases

- Designing Vulkan rendering pipelines, Render Passes, Dynamic Rendering, Render Graphs, or RHI abstractions.
- Implementing or modifying Descriptor, Pipeline, Command Buffer, Buffer/Image, Swapchain, synchronization, and resource lifecycle code.
- Debugging black screens, flickering, crashes, GPU hangs, device lost, Validation Errors, image layouts, descriptor binding, and similar issues.
- Analyzing mobile Vulkan performance bottlenecks, including bandwidth, fullscreen passes, barriers, descriptor updates, and pipeline creation stutter.
- Handling Android Vulkan `ANativeWindow`, Surface lifecycle, pause/resume, orientation changes, and swapchain recreation.
- Distinguishing between specification facts, engineering judgment, and items requiring lookup when API details are uncertain.

## Skill Structure

```text
.
├── SKILL.md                 # Skill entry: triggers, loading order, and output rules
├── agents/                  # Optional tool or platform integration configs
├── assets/                  # Image assets used by README and release pages
└── references/              # Vulkan expert knowledge base, progressively loaded by task
```

`references/` is split into 8 modules by responsibility:

| Module | Purpose |
|---|---|
| `00_expert_entry` | Role, hard rules, task classification, output formats, debugging/performance priorities |
| `01_source_map_and_api_manual_strategy` | Source tiers, citation rules, API card writing strategy |
| `02_core_mental_model` | Vulkan object chains, frame lifecycle, resource lifecycle, synchronization model, engine subsystem architecture and architecture decisions |
| `03_api_manual` | API cards, lifecycle index, error index, and Vulkan API details |
| `04_debug_playbooks` | Playbooks for black screens, flickering, crashes, Validation Errors, synchronization, and performance |
| `05_workflows` | Renderer, Pass, Compute, Android integration, resource management, and optimization workflows |
| `06_cases` | Real engineering cases, misdiagnosis retrospectives, root causes, fixes, and distilled lessons |
| `07_integration_pack` | Module dependencies, task routing, retrieval policy, and token usage rules |

## Core Capabilities

This skill requires output to always provide actionable Vulkan paths rather than stopping at conceptual explanations:

1. Lead with the conclusion and the highest-priority judgment.
2. Provide the Vulkan object chain, key APIs, resource states, layouts, or synchronization relationships.
3. Flag high-risk points such as descriptors, pipelines, command buffers, image layouts, object lifetimes, and the Android lifecycle.
4. Give the minimal verification approach, e.g. Validation Layer, RenderDoc, AGI, logcat, traces, counters, or targeted asserts.
5. Explicitly require looking up the Vulkan Spec, Registry, official samples, or platform docs when API details are uncertain.

## Installation & Usage

This skill follows the Agent Skills specification: the repository root is the skill directory, `SKILL.md` is the entry point, and `references/` is loaded on demand.

**Claude Code**

```bash
git clone https://github.com/oahc09/vulkan-rendering-expert-skill ~/.claude/skills/vulkan-rendering-expert-skill
```

Once placed in the skills directory, describing a Vulkan problem triggers it automatically; you can also explicitly say "use vulkan-rendering-expert-skill".

**TraeCode / Trae**

Add this repository directory as a local skill in skill management, or install it from the skill marketplace.

**Other Agent Skills-compatible hosts** (Cursor, VS Code extensions, etc.)

Any host that reads the `SKILL.md` frontmatter and loads `references/` files per its instructions works. If the host has no skill mechanism, paste the full `SKILL.md` as a system prompt — the skill runs in degraded mode (routing and answer rules still apply; automatic loading does not).

## Example Prompts

The following prompts are ready to copy; each is labeled with the modules it triggers:

1. `Android Vulkan black screen after pause/resume — give the object chain, most likely causes, and verification steps.` (debug playbook + Android case)
2. `vkCreateGraphicsPipelines failed with a VUID error — decode this Validation message: <paste it>` (validation decode playbook)
3. `GPU frame time is 22ms on a Xiaomi 13, dominated by fullscreen post-processing — how do I optimize it?` (performance playbook + optimization workflow)
4. `Build a minimal Vulkan renderer from scratch: validation-clean, resize-safe.` (renderer workflow + architecture decisions)
5. `With thousands of materials, descriptor set creation is slow — should I go bindless? Give me a decision analysis.` (architecture decision framework + bindless case)
6. `Hand-written barriers across 8 passes are getting unmaintainable — evaluate adopting a RenderGraph.` (architecture decision + RenderGraph case)
7. `How should I choose srcStageMask for vkCmdPipelineBarrier2?` (API card)
8. `Any real-world cases of crashes caused by swapchain recreation?` (case index)

Attaching key information yields the most accurate answers — see the per-task-type question templates in section R2 of `references/00_expert_entry/progressive_retrieval.md`.

## Getting Started

- **Just ask (recommended)**: no files to read first — the skill routes by symptom/intent to the matching playbook, workflow, or case.
- **See the knowledge map**: read `references/README.md` and `references/MODULE_SUMMARY.md` for the division of labor across the 8 modules.
- **Deep dive**: read modules in order `00` → `07`; start with `04_debug_playbooks/` for debugging, `05_workflows/` for implementation, and `02_core_mental_model/engine_architecture.md` for architecture.
