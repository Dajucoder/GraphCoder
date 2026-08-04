# Agent Specifications

Each agent in GraphCoder is a specialized node in the LangGraph state machine.
This document describes the role, inputs, outputs, and behavior of each agent.

---

## 1. PM (Product Manager) Agent

**File:** `src/agents/pm.py`

### Purpose
Transform raw user requirements into a structured **Product Requirements Document (PRD)**.

### Input State
```python
{
    "user_request": str,       # Raw requirement from user
    "clarifications": list[str],  # Follow-up questions & answers
}
```

### Output State
```python
{
    "prd": str,                # Structured PRD document
    "acceptance_criteria": list[str],  # Success criteria
    "scope_notes": str,        # Out-of-scope notes
}
```

### Behavior
1. Parse the user request for intent, constraints, and success metrics
2. Generate follow-up questions if the requirement is ambiguous (up to N rounds)
3. Produce a structured PRD with: background, objectives, scope, acceptance criteria
4. Mark the requirement as "ready for architecture" when complete

### Prompt Template
See `src/prompts/pm_prompt.py`

---

## 2. Architect (AD) Agent

**File:** `src/agents/architect.py`

### Purpose
Transform a PRD into a concrete **system architecture and technical design**.

### Input State
```python
{
    "prd": str,
    "acceptance_criteria": list[str],
}
```

### Output State
```python
{
    "architecture": str,       # Architecture description
    "tech_stack": list[str],   # Selected technologies
    "module_plan": str,        # Module decomposition
    "api_spec": str,           # API surface (if applicable)
    "data_model": str,         # Data model (if applicable)
}
```

### Behavior
1. Analyze the PRD for functional and non-functional requirements
2. Select appropriate technologies considering constraints (performance, cost, team)
3. Decompose into modules with clear boundaries and interfaces
4. Define data models and API contracts
5. Output a structured architecture document

### Prompt Template
See `src/prompts/architect_prompt.py`

---

## 3. Developer (Dev) Agent

**File:** `src/agents/developer.py`

### Purpose
Generate implementation code based on the architecture design.

### Input State
```python
{
    "architecture": str,
    "tech_stack": list[str],
    "module_plan": str,
    "review_feedback": str | None,  # From Reviewer (if looping)
    "qa_feedback": str | None,      # From QA (if looping)
}
```

### Output State
```python
{
    "code_files": dict[str, str],   # filename → code content
    "dependencies": list[str],      # pip/package dependencies
    "readme": str,                  # Project README
}
```

### Behavior
1. Read architecture and module plan
2. Generate code file by file, with appropriate file paths
3. If review_feedback is present, address each point
4. If qa_feedback is present, fix identified issues
5. Include a generated README with setup instructions

### Prompt Template
See `src/prompts/developer_prompt.py`

---

## 4. Reviewer Agent

**File:** `src/agents/reviewer.py`

### Purpose
Perform static code review and identify issues before QA.

### Input State
```python
{
    "code_files": dict[str, str],
    "architecture": str,
    "module_plan": str,
}
```

### Output State
```python
{
    "review_passed": bool,
    "review_comments": list[str],   # Structured feedback
    "severity": str,                # "blocker" | "major" | "minor" | "nit"
    "suggested_fixes": dict[str, str],  # file → fix suggestion
}
```

### Behavior
1. Review each code file against the architecture plan
2. Check for: correctness, security issues, performance concerns, style consistency
3. Categorize issues by severity
4. Provide specific, actionable fix suggestions
5. Set `review_passed` to `True` only if no blockers remain

### Prompt Template
See `src/prompts/reviewer_prompt.py`

---

## 5. QA Agent

**File:** `src/agents/qa.py`

### Purpose
Design tests and determine if the implementation is ready.

### Input State
```python
{
    "code_files": dict[str, str],
    "architecture": str,
    "review_comments": list[str],
    "review_passed": bool,
}
```

### Output State
```python
{
    "qa_passed": bool,
    "test_plan": str,              # Test strategy and cases
    "test_code": dict[str, str],   # Generated test files
    "issues_found": list[str],     # Remaining issues
    "loop_back": bool,             # True → loop to Developer
}
```

### Behavior
1. Generate a test plan covering unit, integration, and edge cases
2. Generate test code for the test plan
3. Assess whether the code is ready for delivery
4. If issues remain, set `loop_back = True` and detail the fixes needed
5. Enforce a maximum retry count (e.g., 3) to prevent infinite loops

### Prompt Template
See `src/prompts/qa_prompt.py`

---

## Agent Communication

All agents communicate through the **shared state dict**. There is no direct agent-to-agent messaging. The graph edges define the execution order:

```
PM ──▶ Architect ──▶ Developer ──▶ Reviewer ──▶ QA
                                              │
                                              ├── Pass → Output
                                              └── Fail ──▶ Developer (loop)
```

When QA fails, the Developer receives `review_feedback` and `qa_feedback` in its state input.
