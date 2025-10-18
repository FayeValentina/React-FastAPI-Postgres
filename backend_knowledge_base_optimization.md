# Knowledge Base Module Optimization Guide

This guide summarizes the current pain points observed under `backend/app/modules/knowledge_base/` and proposes concrete refactoring steps. It is intended to help keep the RAG ingestion/retrieval layer maintainable as new features are added.

## 1. Module Layout

**Status: Completed**
- `service.py` now acts as a façade, exposing APIs from `config.py`, `ingestion.py`, `retrieval.py`, and `embeddings.py`.
- Retrieval and ingestion logic live in dedicated modules; language helpers were merged into `language.py`.

**Next Steps**
- Evaluate whether `retrieval.py` should be further decomposed (e.g. pipeline helpers per stage) to keep functions <200 LOC.

## 2. Model Lifecycle

**Status: Completed**
- Embedding and rerank models load lazily through `get_embedder()` / `get_reranker()` in `embeddings.py`.
- `reset_models_for_tests()` allows tests to inject or reload lightweight models.

**Next Steps**
- Provide dependency-injection hooks or protocol interfaces so tests can swap in mock embedders without touching globals.

## 3. Configuration Parsing

**Status: Partially Completed**
- `config.py` introduces `_read_setting` with clamping semantics and centralises `RagSearchConfig` derivation.
- Chunking parameters in `ingest_splitter.py` still rely on repetitive `coerce_value` calls.

**Next Steps**
1. Extract a shared configuration schema for chunking parameters similar to `build_rag_config`.
2. Document supported keys and ranges in developer docs for operational visibility.

## 4. Language Utilities

**Status: Completed**
- `language_utils.py` and `ingest_language.py` merged into `language.py`, exposing `normalize_language_value`, `detect_language`, `is_probable_code`, etc.
- All ingestion/retrieval modules now import from this single source.

**Next Steps**
- Add focused tests covering multilingual detection, code fences, and Lingua availability scenarios.

## 5. Retrieval Pipeline Complexity

**Status: Ongoing**
- Retrieval logic moved to `retrieval.py`, but the file still contains multiple large helper functions (`_apply_bm25_fusion`, `_mmr_select`, `search_similar_chunks`).

**Next Steps**
1. Break the pipeline into composable stages (vector recall, BM25 fusion, rerank, MMR) with clear inputs/outputs.
2. Consolidate logging/telemetry into a dedicated helper to standardise structured logs.
3. Explore immutable data structures for candidate bookkeeping to simplify reasoning.

## 6. Testing & Documentation

**Status: Pending**
- No new tests were added as part of the refactor; current coverage still relies on higher-level flows.
- Developer docs updated (`doc/modules/knowledge_base/service.md`) to describe the new module layout.

**Next Steps**
1. Author unit tests for configuration parsing, ingestion persistence, BM25 fusion, and MMR selection.
2. Provide fixtures/mocks that bypass heavyweight model loading (use `reset_models_for_tests()`).
3. Extend documentation with testing guidance and module-level entry points.
