## 1. Dependency and Skeleton

- [x] 1.1 Add `openhands-tools` to pyproject.toml dependencies
- [x] 1.2 Verify DelegateTool import from `openhands.tools.delegate`
- [x] 1.3 Create `src/mattermost_summarizer/subagents/` package
- [x] 1.4 Create `subagents/__init__.py` with package exports
- [x] 1.5 Create stub factory functions for all four sub-agents (returning agents with no tools)
- [x] 1.6 Register stub sub-agents via `register_agent()` in a setup function
- [x] 1.7 Verify sub-agent registration works at startup
- [x] 1.8 Verify delegation flow (spawn + delegate) works with stub agents

## 2. Sub-agent Implementation

- [x] 2.1 Implement `create_thread_fetcher(llm)` factory function with FetchThread, GetUser, FetchChannel tools
- [x] 2.2 Implement `create_bug_researcher(llm)` factory function with FetchLaunchpadBug tool
- [x] 2.3 Implement `create_github_researcher(llm)` factory function with FetchGitHubIssue tool
- [x] 2.4 Implement `create_file_fetcher(llm)` factory function with FetchFile tool
- [x] 2.5 Write focused system prompts for each sub-agent in their factory
- [x] 2.6 Update sub-agent registration to use real factory functions
- [x] 2.7 Verify single-level delegation works (thread_fetcher → orchestrator)

## 3. Orchestrator Implementation

- [x] 3.1 Create `build_orchestrator_agent()` in agent.py with DelegateTool and finish tool
- [x] 3.2 Move system prompt to `AgentContext.system_message_suffix`
- [x] 3.3 Implement orchestrator coordination loop in summarizer.py
- [x] 3.4 Wire orchestrator into `MattermostSummarizer.summarize()`
- [x] 3.5 Verify orchestrator delegates to thread_fetcher correctly
- [x] 3.6 Verify multi-level delegation works (orchestrator → sub-agents → results)

## 4. Recursive Reference Following

- [x] 4.1 Implement URL classification logic in orchestrator (Mattermost vs Launchpad vs GitHub vs file)
- [x] 4.2 Implement LLM-driven reference scanning (orchestrator reads fetched text, identifies URLs)
- [x] 4.3 Implement depth tracking (current_depth, max_reference_depth)
- [x] 4.4 Implement cycle prevention (track followed URLs per summary operation)
- [x] 4.5 Implement delegation routing (URL type → appropriate sub-agent)
- [x] 4.6 Test depth 1 (no recursion, thread only)
- [x] 4.7 Test depth 2 (one referenced thread or bug followed)
- [x] 4.8 Test depth 3 (thread → thread → thread chain)
- [x] 4.9 Verify depth limit stops recursion correctly

## 5. Critic Implementation

- [x] 5.1 Create `src/mattermost_summarizer/critic.py`
- [x] 5.2 Implement `SummarizationCritic(CriticBase)` class
- [x] 5.3 Implement `_extract_gathered_context(events)` to read delegation results
- [x] 5.4 Implement `_extract_finish_action(events)` to read produced summary
- [x] 5.5 Implement `_build_rubric(level)` for level-specific evaluation prompts
- [x] 5.6 Implement `_call_critic_llm(context, summary, rubric)` for LLM evaluation
- [x] 5.7 Configure `iterative_refinement` with default threshold 0.7, max 2 iterations
- [x] 5.8 Wire critic into orchestrator agent
- [x] 5.9 Test critic evaluates summary and returns score
- [x] 5.10 Test iterative refinement loop (revision when below threshold)

## 6. Configuration

- [x] 6.1 Add `[summarizer]` TOML section to config.py
- [x] 6.2 Add fields: max_reference_depth (default 3), critic_enabled (default true), critic_threshold (default 0.7), critic_max_iterations (default 2)
- [x] 6.3 Add environment variable support (MM_SUMMARIZER_MAX_REFERENCE_DEPTH, etc.)
- [x] 6.4 Update `MattermostSummarizerConfig.from_config()` to parse [summarizer] section
- [x] 6.5 Pass config values to orchestrator and critic
- [x] 6.6 Test TOML config with all new fields
- [x] 6.7 Test env var override for all new fields

## 7. Integration and Cleanup

- [x] 7.1 Update tools/__init__.py to reflect new tool distribution (sub-agents get tools, orchestrator gets DelegateTool)
- [x] 7.2 Update summarize.py CLI if needed for new config options
- [x] 7.3 Run ruff check and fix any linting issues
- [x] 7.4 Run mypy and pyright, fix any type errors
- [x] 7.5 Write integration tests for multi-agent flow
- [x] 7.6 Write tests for recursive reference following
- [x] 7.7 Write tests for critic evaluation
- [x] 7.8 Run full test suite
- [x] 7.9 Update existing tests that relied on single-agent architecture
- [x] 7.10 Verify agent-trace.log is readable with delegation output